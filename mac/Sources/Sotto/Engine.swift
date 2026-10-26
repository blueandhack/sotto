import Foundation
import Observation
import ServiceManagement

/// The engine bundled in Sotto.app (bundle-runtime.sh): sotto's Python runtime, pf-serve, and the
/// background service that runs `sotto serve`. Everything goes through the bundled `sotto`
/// command, so the app and the CLI share one implementation of setup and protection.
@MainActor
@Observable
final class Engine {
    /// `sotto status --json`.
    struct Status: Decodable, Equatable {
        struct Protect: Decodable, Equatable {
            var settings: String?
            var on: Bool?
            var baseUrl: String?
            var error: String?
        }
        var model: String?
        var modelSize: Int
        var pfServe: String?
        var protect: Protect
        var port: Int
        var serveRunning: Bool
        var excluded: [Excluded] = []
    }

    /// A project sent straight to the API, around sotto (`sotto exclude`).
    struct Excluded: Decodable, Equatable, Identifiable {
        var path: String
        var url: String
        var active: Bool
        var id: String { path }
    }

    private(set) var status: Status?
    private(set) var serviceStatus: SMAppService.Status = .notRegistered
    /// 0...1 while the model downloads.
    private(set) var download: Double?
    private(set) var busy = false
    var error: String?
    /// The menu bar asks the dashboard to open on Settings, where Setup is.
    var settingsRequested = false

    /// Contents/Resources/sotto. Missing when the app was built without the engine (SKIP_RUNTIME).
    let cli = Bundle.main.url(forResource: "sotto", withExtension: nil)
    private let service = SMAppService.agent(plistName: "dev.sotto.agent.plist")
    private var task: Task<Void, Never>?

    private(set) var previewing = false
    var isBundled: Bool { cli != nil || previewing }
    var hasModel: Bool { status?.model != nil }
    var serviceRunning: Bool { status?.serveRunning == true }
    var protected: Bool { status?.protect.on == true }
    var setupDone: Bool { hasModel && serviceRunning && protected }

    func start() {
        guard task == nil, isBundled else { return }
        task = Task { [weak self] in
            await self?.reregisterAfterUpdate()
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(for: .seconds(15))
            }
        }
    }

    func refresh() async {
        serviceStatus = service.status
        guard let out = try? await run(["status", "--json"]), out.code == 0 else { return }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        if let s = try? decoder.decode(Status.self, from: Data(out.stdout.utf8)) { status = s }
    }

    /// `sotto setup`: the model, once, with progress from its "NN% of 1.6 GB" lines.
    func downloadModel() async {
        await act {
            self.download = 0
            defer { self.download = nil }
            let out = try await self.run(["setup"]) { line in
                if let pct = line.split(separator: "%").first.flatMap({ Double($0.trimmingCharacters(in: .whitespaces)) }) {
                    Task { @MainActor in self.download = pct / 100 }
                }
            }
            if out.code != 0 { throw EngineError(out.lastLine) }
        }
    }

    /// Register the LaunchAgent. macOS may ask the user to allow it in Login Items first.
    func startService() async {
        await act {
            do {
                try self.service.register()
            } catch let e as NSError where e.code == Int(kSMErrorAlreadyRegistered) {
                // already registered: fine
            }
            UserDefaults.standard.set(Self.version, forKey: "registeredVersion")
            if self.service.status == .requiresApproval { SMAppService.openSystemSettingsLoginItems() }
            try? await Task.sleep(for: .seconds(2))  // let the proxy load the model
        }
    }

    /// Stopping the service while Claude Code is pointed at it would cut Claude Code off: turn
    /// protection off first.
    func stopService() async {
        await act {
            if self.protected { try await self.applyProtection(false) }
            try await self.service.unregister()
        }
    }

    func setProtection(_ on: Bool) async {
        await act { try await self.applyProtection(on) }
    }

    private func applyProtection(_ on: Bool) async throws {
        if on && !serviceRunning { throw EngineError("Start the background service first.") }
        let out = try await run(["protect", on ? "on" : "off"])
        if out.code != 0 { throw EngineError(out.lastLine) }
    }

    func openLoginItems() { SMAppService.openSystemSettingsLoginItems() }

    /// The result of the last exclude or include, for the card to show.
    var exclusionNote: String?

    func exclude(_ folder: URL) async {
        await act {
            let out = try await self.run(["exclude", folder.path])
            if out.code != 0 { throw EngineError(out.lastLine) }
            self.exclusionNote = "Excluded. It applies once Claude Code trusts the folder."
        }
    }

    func include(_ path: String) async {
        await act {
            let out = try await self.run(["include", path])
            if out.code != 0 { throw EngineError(out.lastLine) }
            self.exclusionNote = "Scanned again. Restart Claude Code sessions open in that project."
        }
    }

    // MARK: -

    private static let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"

    /// launchd keeps running the old executable after an update until the agent is registered again.
    private func reregisterAfterUpdate() async {
        guard service.status == .enabled, UserDefaults.standard.string(forKey: "registeredVersion") != Self.version else { return }
        try? await service.unregister()
        try? service.register()
        UserDefaults.standard.set(Self.version, forKey: "registeredVersion")
    }

    private func act(_ body: @escaping @MainActor () async throws -> Void) async {
        guard !busy else { return }
        busy = true
        error = nil
        do { try await body() } catch { self.error = (error as? EngineError)?.message ?? error.localizedDescription }
        await refresh()
        busy = false
    }

    struct Output {
        var code: Int32
        var stdout: String
        var stderr: String
        var lastLine: String {
            stderr.split(whereSeparator: { $0 == "\n" || $0 == "\r" }).last.map(String.init) ?? "sotto exited with \(code)"
        }
    }

    /// Run the bundled `sotto` off the main thread. `onLine` sees stderr lines as they arrive.
    private func run(_ args: [String], onLine: (@Sendable (String) -> Void)? = nil) async throws -> Output {
        guard let cli else { throw EngineError("This copy of Sotto has no bundled engine.") }
        return try await Task.detached {
            let p = Process()
            p.executableURL = cli
            p.arguments = args
            let out = Pipe(), err = Pipe()
            p.standardOutput = out
            p.standardError = err
            let collected = LockedData()
            err.fileHandleForReading.readabilityHandler = { h in
                let chunk = h.availableData
                collected.append(chunk)
                if let onLine, let text = String(data: chunk, encoding: .utf8) {
                    for line in text.split(whereSeparator: { $0 == "\n" || $0 == "\r" }) { onLine(String(line)) }
                }
            }
            try p.run()
            let stdout = out.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            err.fileHandleForReading.readabilityHandler = nil
            collected.append(err.fileHandleForReading.readDataToEndOfFile())
            return Output(code: p.terminationStatus, stdout: String(decoding: stdout, as: UTF8.self),
                          stderr: String(decoding: collected.data, as: UTF8.self))
        }.value
    }

    /// For snapshots: an engine that is set up and protecting Claude Code.
    static func preview() -> Engine {
        let e = Engine()
        e.previewing = true
        e.status = Status(model: "~/.local/share/sotto/models/privacy-filter-q8.gguf", modelSize: 1_637_572_192,
                          pfServe: "Sotto.app/Contents/Resources/bin/pf-serve",
                          protect: .init(settings: "~/.claude/settings.json", on: true, baseUrl: "http://127.0.0.1:7788"),
                          port: 7788, serveRunning: true,
                          excluded: [.init(path: "~/Projects/open-source-docs", url: "https://api.anthropic.com", active: true)])
        e.serviceStatus = .enabled
        return e
    }
}

struct EngineError: Error {
    var message: String
    init(_ message: String) { self.message = message }
}

private final class LockedData: @unchecked Sendable {
    private let lock = NSLock()
    private(set) var data = Data()
    func append(_ d: Data) { lock.lock(); data.append(d); lock.unlock() }
}
