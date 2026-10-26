import AppKit
import IOKit.ps
import SwiftUI

extension Color {
    /// A color that follows the light or dark appearance it is drawn in.
    init(light: NSColor, dark: NSColor) {
        self.init(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
        })
    }
}

extension NSColor {
    convenience init(hex: UInt32, alpha: CGFloat = 1) {
        self.init(srgbRed: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255, alpha: alpha)
    }
}

/// A small palette: one accent, neutrals, and two signal colors (restored, blocked).
enum Theme {
    static let background = Color(light: NSColor(hex: 0xF5F6F8), dark: NSColor(hex: 0x0F1115))
    static let sidebar = Color(light: NSColor(hex: 0xECEEF2), dark: NSColor(hex: 0x15181E))
    static let surface = Color(light: .white, dark: NSColor(hex: 0x1A1D24))
    static let border = Color(light: NSColor(hex: 0x000000, alpha: 0.08), dark: NSColor(hex: 0xFFFFFF, alpha: 0.08))
    static let text = Color(light: NSColor(hex: 0x16181D), dark: NSColor(hex: 0xECEEF2))
    static let secondary = Color(light: NSColor(hex: 0x6B7280), dark: NSColor(hex: 0x8B93A1))
    static let faint = Color(light: NSColor(hex: 0x000000, alpha: 0.05), dark: NSColor(hex: 0xFFFFFF, alpha: 0.06))
    static let accent = Color(light: NSColor(hex: 0x4F5BD5), dark: NSColor(hex: 0x7C86FF))
    static let accentSoft = Color(light: NSColor(hex: 0x4F5BD5, alpha: 0.10), dark: NSColor(hex: 0x7C86FF, alpha: 0.16))
    static let success = Color(light: NSColor(hex: 0x16A34A), dark: NSColor(hex: 0x34D399))
    static let danger = Color(light: NSColor(hex: 0xDC2626), dark: NSColor(hex: 0xF87171))
    static let placeholder = Color(light: NSColor(hex: 0x9CA3AF), dark: NSColor(hex: 0x6B7280))

    static let typeOrder = ["SECRET", "ACCOUNT", "PERSON", "EMAIL", "PHONE", "ADDRESS", "URL", "DATE"]

    static func label(_ type: String) -> String {
        switch type {
        case "SECRET": "Secrets"
        case "ACCOUNT": "Accounts"
        case "PERSON": "Names"
        case "EMAIL": "Emails"
        case "PHONE": "Phones"
        case "ADDRESS": "Addresses"
        case "URL": "URLs"
        case "DATE": "Dates"
        default: type.capitalized
        }
    }

    static func icon(_ type: String) -> String {
        switch type {
        case "SECRET": "key.fill"
        case "ACCOUNT": "creditcard.fill"
        case "PERSON": "person.fill"
        case "EMAIL": "envelope.fill"
        case "PHONE": "phone.fill"
        case "ADDRESS": "house.fill"
        case "URL": "link"
        case "DATE": "calendar"
        default: "circle.fill"
        }
    }
}

enum Appearance: String, CaseIterable, Identifiable {
    case system, light, dark
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
    var scheme: ColorScheme? {
        switch self {
        case .system: nil
        case .light: .light
        case .dark: .dark
        }
    }
}

struct Card<Content: View, Accessory: View>: View {
    var title: String
    var subtitle: String?
    @ViewBuilder var accessory: Accessory
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.text)
                    if let subtitle { Text(subtitle).font(.system(size: 11)).foregroundStyle(Theme.secondary) }
                }
                Spacer(minLength: 8)
                accessory
            }
            content
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(Theme.border))
    }
}

extension Card where Accessory == EmptyView {
    init(title: String, subtitle: String? = nil, @ViewBuilder content: () -> Content) {
        self.init(title: title, subtitle: subtitle, accessory: { EmptyView() }, content: content)
    }
}

/// A capsule button drawn in SwiftUI, so it looks the same in both appearances and in snapshots.
struct PillButton: View {
    var title: String
    var icon: String? = nil
    var prominent = false
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if let icon { Image(systemName: icon).font(.system(size: 11, weight: .semibold)) }
                Text(title).font(.system(size: 12, weight: .medium)).lineLimit(1)
            }
            .fixedSize()
            .foregroundStyle(prominent ? Color.white : Theme.text)
            .padding(.horizontal, 12).padding(.vertical, 6)
            .background(Capsule().fill(prominent ? AnyShapeStyle(Theme.accent) : AnyShapeStyle(Theme.faint)))
            .overlay(Capsule().strokeBorder(prominent ? Color.clear : Theme.border))
        }
        .buttonStyle(.plain)
    }
}

/// A segmented control drawn in SwiftUI.
struct Segmented<T: Hashable>: View {
    var options: [(T, String)]
    @Binding var selection: T

    var body: some View {
        HStack(spacing: 2) {
            ForEach(options, id: \.0) { value, title in
                Button { selection = value } label: {
                    Text(title).font(.system(size: 12, weight: .medium))
                        .foregroundStyle(selection == value ? Theme.text : Theme.secondary)
                        .padding(.horizontal, 14).padding(.vertical, 5)
                        .background(Capsule().fill(selection == value ? Theme.surface : .clear))
                        .shadow(color: .black.opacity(selection == value ? 0.08 : 0), radius: 1, y: 1)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(Capsule().fill(Theme.faint))
    }
}

struct StatusDot: View {
    var connection: Connection

    var body: some View {
        let (text, color) = info
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(text).font(.system(size: 11.5, weight: .medium)).foregroundStyle(Theme.secondary)
        }
    }

    private var info: (String, Color) {
        switch connection {
        case .live: ("Live", Theme.success)
        case .sample: ("Preview data", Theme.accent)
        case .connecting: ("Connecting", Theme.placeholder)
        case .offline: ("Offline", Theme.danger)
        }
    }
}

extension Int {
    var compact: String {
        switch self {
        case 1_000_000...: String(format: "%.1fM", Double(self) / 1_000_000)
        case 10_000...: String(format: "%.0fk", Double(self) / 1_000)
        case 1_000...: String(format: "%.1fk", Double(self) / 1_000)
        default: "\(self)"
        }
    }
}

func durationText(_ seconds: Double) -> String {
    let s = Int(seconds)
    if s < 60 { return "\(s)s" }
    if s < 3600 { return "\(s / 60)m" }
    return "\(s / 3600)h \(s % 3600 / 60)m"
}

func percent(_ part: Int, of whole: Int) -> String {
    whole > 0 ? String(format: "%.0f%%", Double(part) / Double(whole) * 100) : "—"
}

/// Logos. The Claude and Anthropic logos (mac/Brand, from Anthropic's press kit; see
/// Brand/NOTICE.md) identify the services sotto works with. build-app.sh copies them into the
/// app; when running from the build folder they are found in mac/Brand.
enum Brand {
    static func logo(_ name: String) -> NSImage? {
        if let url = Bundle.main.url(forResource: name, withExtension: "png") { return NSImage(contentsOf: url) }
        var dir = Bundle.main.bundleURL
        for _ in 0..<5 {
            dir = dir.deletingLastPathComponent()
            let candidate = dir.appending(path: "Brand/\(name).png")
            if FileManager.default.fileExists(atPath: candidate.path) { return NSImage(contentsOf: candidate) }
        }
        return nil
    }

    /// A laptop when this Mac has a battery, otherwise a Mac mini.
    static let thisMacSymbol: String = {
        let info = IOPSCopyPowerSourcesInfo()?.takeRetainedValue()
        let list = info.flatMap { IOPSCopyPowerSourcesList($0)?.takeRetainedValue() as? [CFTypeRef] } ?? []
        return list.isEmpty ? "macmini" : "laptopcomputer"
    }()
}

/// The sotto mark: three lines of text where one word became placeholders. The first square is
/// solid ("the masked value"). Drawn in a 100x100 box at any size, in one color, so it works as
/// an app icon, a template image in the menu bar, and a small logo.
struct SottoMark: View {
    var color: Color = .white

    var body: some View {
        GeometryReader { geo in
            let u = min(geo.size.width, geo.size.height) / 100
            VStack(alignment: .leading, spacing: 12 * u) {
                Capsule().fill(color).frame(width: 62 * u, height: 11 * u)
                HStack(spacing: 6 * u) {
                    Capsule().fill(color).frame(width: 18 * u, height: 11 * u)
                    ForEach(0..<3, id: \.self) { i in
                        RoundedRectangle(cornerRadius: 3.4 * u, style: .continuous)
                            .fill(color.opacity(i == 0 ? 1 : 0.5))
                            .frame(width: 11 * u, height: 11 * u)
                    }
                }
                Capsule().fill(color).frame(width: 44 * u, height: 11 * u)
            }
            .frame(width: geo.size.width, height: geo.size.height)
        }
    }
}

/// The mark on the accent squircle: the app icon's look, at small sizes.
struct SottoBadge: View {
    var size: CGFloat

    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.3, style: .continuous)
            .fill(LinearGradient(colors: [Color(nsColor: NSColor(hex: 0x5B66E0)), Color(nsColor: NSColor(hex: 0x3F49C2))],
                                 startPoint: .top, endPoint: .bottom))
            .overlay(SottoMark(color: .white).padding(size * 0.17))
            .frame(width: size, height: size)
    }
}

extension Brand {
    /// The mark as a template image for the menu bar: macOS tints it for light and dark.
    /// Rendered once per variant; the menu bar label updates every second.
    @MainActor static let menuBarActive = renderMenuBarImage(dimmed: false)
    @MainActor static let menuBarIdle = renderMenuBarImage(dimmed: true)

    @MainActor private static func renderMenuBarImage(dimmed: Bool) -> NSImage {
        let renderer = ImageRenderer(content: SottoMark(color: .black.opacity(dimmed ? 0.45 : 1)).frame(width: 18, height: 18))
        renderer.scale = 2
        let image = renderer.nsImage ?? NSImage(systemSymbolName: "text.alignleft", accessibilityDescription: nil)!
        image.size = NSSize(width: 18, height: 18)
        image.isTemplate = true
        return image
    }
}
