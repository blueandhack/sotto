import AppKit
import SwiftUI

@main
struct SottoApp: App {
    @State private var store = StatsStore()

    init() {
        Snapshotter.runIfRequested()
    }

    var body: some Scene {
        MenuBarExtra {
            MenuPanel(store: store)
        } label: {
            MenuLabel(store: store)
        }
        .menuBarExtraStyle(.window)

        Window("sotto", id: "dashboard") {
            Dashboard(store: store)
                .frame(minWidth: 1100, minHeight: 720)
                .onAppear { store.start() }
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1200, height: 780)
    }
}

struct MenuLabel: View {
    var store: StatsStore

    var body: some View {
        let unique = store.snapshot.vaultSize ?? 0
        HStack(spacing: 3) {
            Image(nsImage: store.connection == .live || store.connection == .sample ? Brand.menuBarActive : Brand.menuBarIdle)
            if unique > 0 { Text(unique.compact).monospacedDigit() }
        }
        .task { store.start() }
    }
}

struct MenuPanel: View {
    @Bindable var store: StatsStore
    @AppStorage("appearance") private var appearance: Appearance = .system
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        let s = store.snapshot
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 8) {
                SottoBadge(size: 24)
                Text("sotto").font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.text)
                Spacer()
                StatusDot(connection: store.connection)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text((s.vaultSize ?? 0).compact).font(.system(size: 32, weight: .semibold, design: .rounded)).monospacedDigit()
                    .foregroundStyle(Theme.text).contentTransition(.numericText())
                Text("unique values kept on this Mac").font(.system(size: 12)).foregroundStyle(Theme.secondary)
            }
            HStack(spacing: 0) {
                stat("Requests", s.contentRequests.compact)
                stat("Sensitive", s.funnel.withFindings.compact)
                stat("Blocked", s.blocked.compact, color: s.blocked > 0 ? Theme.danger : Theme.text)
                stat("p95", s.scanMs.p95.map { String(format: "%.0f ms", $0) } ?? "—")
            }
            .padding(.vertical, 12)
            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.faint))
            if case .offline(let reason) = store.connection {
                Text("\(reason). Run sotto claude to start.").font(.system(size: 11.5)).foregroundStyle(Theme.secondary)
            }
            HStack(spacing: 8) {
                PillButton(title: "Open dashboard", icon: "macwindow", prominent: true) {
                    openWindow(id: "dashboard")
                    NSApp.activate()
                }
                PillButton(title: store.sampleMode ? "Live" : "Preview", icon: store.sampleMode ? "dot.radiowaves.left.and.right" : "sparkles") {
                    store.sampleMode.toggle()
                }
                Spacer()
                PillButton(title: "Quit") { NSApp.terminate(nil) }
            }
        }
        .padding(16)
        .frame(width: 330)
        .background(Theme.background)
        .preferredColorScheme(appearance.scheme)
    }

    private func stat(_ title: String, _ value: String, color: Color = Theme.text) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.system(size: 14, weight: .semibold, design: .rounded)).monospacedDigit().foregroundStyle(color)
            Text(title).font(.system(size: 10.5)).foregroundStyle(Theme.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

/// Renders the app to PNGs and exits, to check the design without a screen.
///   `Sotto --snapshot dir`         every page in light and dark, with preview data
///   `Sotto --snapshot dir --live`  the overview from the running sotto's stats feed
///   `Sotto --icon dir`             the app icon at every size iconutil needs
@MainActor
enum Snapshotter {
    static func runIfRequested() {
        let args = CommandLine.arguments
        if let i = args.firstIndex(of: "--icon"), i + 1 < args.count {
            _ = NSApplication.shared
            for (name, px) in [("16x16", 16), ("16x16@2x", 32), ("32x32", 32), ("32x32@2x", 64), ("128x128", 128),
                               ("128x128@2x", 256), ("256x256", 256), ("256x256@2x", 512), ("512x512", 512), ("512x512@2x", 1024)] {
                render(AppIcon().frame(width: 1024, height: 1024).scaleEffect(CGFloat(px) / 1024).frame(width: CGFloat(px), height: CGFloat(px)),
                       to: "\(args[i + 1])/icon_\(name).png", dark: false, scale: 1)
            }
            exit(0)
        }
        guard let i = args.firstIndex(of: "--snapshot"), i + 1 < args.count else { return }
        _ = NSApplication.shared
        let dir = args[i + 1]
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        let store = StatsStore()
        if args.contains("--live") {
            let done = DispatchSemaphore(value: 0)
            Task { @MainActor in
                await store.refresh()
                done.signal()
            }
            while done.wait(timeout: .now()) == .timedOut { RunLoop.main.run(until: Date().addingTimeInterval(0.05)) }
            for dark in [false, true] {
                render(window(store, .overview), to: "\(dir)/live-overview-\(dark ? "dark" : "light").png", dark: dark)
            }
            exit(store.connection == .live ? 0 : 1)
        }
        store.sampleMode = true
        var feed = SampleFeed()
        store.snapshot = feed.next()
        store.connection = .sample
        let now = Date()
        store.pulses = (0..<12).map { k in
            let kinds: [Pulse.Kind] = [.masked("SECRET"), .clean, .masked("EMAIL"), .restored("SECRET"), .clean, .blocked]
            return Pulse(kind: kinds[k % kinds.count], born: now.addingTimeInterval(-Double(k) * 0.19))
        }
        for page in Page.allCases {
            for dark in [false, true] {
                render(window(store, page), to: "\(dir)/\(page.rawValue)-\(dark ? "dark" : "light").png", dark: dark)
            }
        }
        for dark in [false, true] {
            render(MenuPanel(store: store), to: "\(dir)/menu-\(dark ? "dark" : "light").png", dark: dark)
        }
        exit(0)
    }

    /// The dashboard at its default window size: what fits without scrolling is what you see.
    private static func window(_ store: StatsStore, _ page: Page) -> some View {
        Dashboard(store: store, page: page).frame(width: 1200, height: 780)
    }

    private static func render(_ view: some View, to path: String, dark: Bool, scale: CGFloat = 2) {
        NSApp.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
        let renderer = ImageRenderer(content: view.environment(\.colorScheme, dark ? .dark : .light))
        renderer.scale = scale
        guard let image = renderer.nsImage, let tiff = image.tiffRepresentation,
              let png = NSBitmapImageRep(data: tiff)?.representation(using: .png, properties: [:]) else {
            FileHandle.standardError.write("snapshot failed: \(path)\n".data(using: .utf8)!)
            exit(1)
        }
        try? png.write(to: URL(fileURLWithPath: path))
    }
}

/// The app icon: the sotto mark (a line of text with a word masked) on an indigo squircle.
struct AppIcon: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 230, style: .continuous)
                .fill(LinearGradient(colors: [Color(nsColor: NSColor(hex: 0x5B66E0)), Color(nsColor: NSColor(hex: 0x3A44B8))],
                                     startPoint: .top, endPoint: .bottom))
                .padding(100)
            RoundedRectangle(cornerRadius: 230, style: .continuous)
                .strokeBorder(Color.white.opacity(0.12), lineWidth: 4)
                .padding(100)
            SottoMark(color: .white)
                .frame(width: 560, height: 560)
                .shadow(color: .black.opacity(0.18), radius: 12, y: 8)
        }
        .frame(width: 1024, height: 1024)
    }
}
