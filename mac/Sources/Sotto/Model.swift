import Foundation
import Observation

/// The stats feed from `GET /_sotto/stats`. Counts, types and timestamps only: the feed
/// never carries a sensitive value or a placeholder, so this app cannot show one.
struct Snapshot: Decodable, Sendable {
    struct Funnel: Decodable, Sendable {
        var requests = 0, scanned = 0, withFindings = 0, masked = 0, restored = 0
    }
    struct Minute: Decodable, Sendable, Identifiable {
        var t: Double
        var requests: Int
        var masked: [String: Int]
        var restored: Int
        var blocked: Int
        var id: Double { t }
        var date: Date { Date(timeIntervalSince1970: t) }
    }
    struct Latency: Decodable, Sendable { var p50: Double?, p95: Double?, n: Int = 0 }
    struct Event: Decodable, Sendable, Identifiable {
        var ts: Double
        var path: String
        var outcome: String
        var status: Int
        var scanMs: Double?
        var redacted: [String: Int]
        var restored: [String: Int]
        var id: Double { ts }
        var date: Date { Date(timeIntervalSince1970: ts) }
    }

    var started: Double = Date().timeIntervalSince1970
    var uptimeS: Double = 0
    var requests: [String: Int] = [:]
    var redacted: [String: Int] = [:]
    var restored: [String: Int] = [:]
    var funnel = Funnel()
    var detection: [String: Int] = [:]
    var timeline: [Minute] = []
    var scanMs = Latency()
    var recent: [Event] = []
    var upstream: String?
    var vaultSize: Int?
    var mode: String?
    var pii: Bool?
    var detector: String?
    var version: String?

    /// How sotto was started: `sotto claude`, `sotto serve`, or an editor's wrapper.
    var modeLabel: String {
        switch mode {
        case "claude": "sotto claude"
        case "vscode": "VS Code"
        case "serve": "sotto serve"
        default: "—"
        }
    }

    /// Computed from `started`, so it keeps ticking between polls.
    var uptime: Double { max(0, Date().timeIntervalSince1970 - started) }
    /// Requests that carried content: scanned, or blocked before scanning. Bodyless checks
    /// such as `HEAD /api/hello` are forwarded but not counted here.
    var contentRequests: Int { funnel.scanned + blocked }
    var blocked: Int { (requests["blocked"] ?? 0) + (requests["rejected"] ?? 0) }
    var maskedTotal: Int { redacted.values.reduce(0, +) }
    var restoredTotal: Int { restored.values.reduce(0, +) }
}

enum Connection: Equatable {
    case connecting, live, offline(String), sample
}

/// A short-lived visual event for the flow diagram.
struct Pulse: Identifiable, Sendable {
    enum Kind: Sendable { case clean, masked(String), restored(String), blocked }
    let id = UUID()
    let kind: Kind
    let born: Date
}

@MainActor
@Observable
final class StatsStore {
    var snapshot = Snapshot()
    var connection: Connection = .connecting
    var pulses: [Pulse] = []
    var sampleMode = false {
        didSet { if sampleMode { sample = SampleFeed() } }
    }

    private var sample = SampleFeed()
    private var task: Task<Void, Never>?
    private let home = FileManager.default.homeDirectoryForCurrentUser
    private var lastEventTs: Double = 0
    private(set) var port = 7788

    func start() {
        guard task == nil else { return }
        task = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }

    func refresh() async {
        if sampleMode {
            apply(sample.next(), connection: .sample)
            return
        }
        guard let token = try? String(contentsOf: home.appending(path: ".config/sotto/stats-token"), encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines), !token.isEmpty
        else {
            connection = .offline("sotto has not run yet")
            return
        }
        port = discoverPort()
        var request = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/_sotto/stats")!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 2
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                connection = .offline("sotto refused the stats token")
                return
            }
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            apply(try decoder.decode(Snapshot.self, from: data), connection: .live)
        } catch {
            connection = .offline("sotto is not running")
        }
    }

    /// The port of the running proxy: runtime.json (written by sotto claude/serve) or 7788.
    private func discoverPort() -> Int {
        struct Runtime: Decodable { var pid: Int32; var port: Int }
        if let data = try? Data(contentsOf: home.appending(path: ".config/sotto/runtime.json")),
           let rt = try? JSONDecoder().decode(Runtime.self, from: data), kill(rt.pid, 0) == 0 {
            return rt.port
        }
        return 7788
    }

    private func apply(_ new: Snapshot, connection: Connection) {
        let now = Date()
        for event in new.recent where event.ts > lastEventTs {
            if event.outcome == "blocked" || event.outcome == "rejected" {
                pulses.append(Pulse(kind: .blocked, born: now))
            } else if event.redacted.isEmpty {
                pulses.append(Pulse(kind: .clean, born: now))
            }
            for (type, n) in event.redacted { for _ in 0..<min(n, 3) { pulses.append(Pulse(kind: .masked(type), born: now)) } }
            for (type, n) in event.restored { for _ in 0..<min(n, 3) { pulses.append(Pulse(kind: .restored(type), born: now)) } }
        }
        lastEventTs = max(lastEventTs, new.recent.last?.ts ?? 0)
        pulses.removeAll { now.timeIntervalSince($0.born) > FlowGeometry.lifetime }
        snapshot = new
        self.connection = connection
    }
}

/// Synthetic numbers for previews, screenshots, and the snapshot renderer. Not real traffic.
struct SampleFeed {
    private var snap = Snapshot()
    private var tick = 0

    init() {
        let now = Date().timeIntervalSince1970
        snap.started = now - 5400
        snap.mode = "claude"; snap.pii = true; snap.detector = "rules+pf-serve"; snap.version = "0.0.1"
        snap.upstream = "https://api.anthropic.com"
        let weights: [(String, Int)] = [("SECRET", 5), ("EMAIL", 3), ("PERSON", 3), ("PHONE", 1), ("ACCOUNT", 1)]
        for i in stride(from: 89, through: 0, by: -1) {  // more than the hour on screen, like the real feed
            var masked: [String: Int] = [:]
            let burst = (i % 9 == 0) ? 3 : 1
            for (t, w) in weights where Int.random(in: 0..<10) < w * burst { masked[t, default: 0] += Int.random(in: 1...3) }
            let reqs = Int.random(in: 2...9)
            snap.timeline.append(.init(t: (now / 60).rounded(.down) * 60 - Double(i * 60), requests: reqs, masked: masked,
                                       restored: masked.values.reduce(0, +) / 2, blocked: i == 17 ? 1 : 0))
        }
        for m in snap.timeline {
            for (k, v) in m.masked { snap.redacted[k, default: 0] += v }
            snap.restored["SECRET", default: 0] += m.restored
            snap.funnel.requests += m.requests
        }
        snap.requests = ["forwarded": snap.funnel.requests - 2, "blocked": 1, "rejected": 1]
        snap.funnel.scanned = snap.funnel.requests - 2
        snap.funnel.withFindings = Int(Double(snap.funnel.scanned) * 0.34)
        snap.funnel.masked = snap.maskedTotal
        snap.funnel.restored = snap.restoredTotal
        let masked = snap.maskedTotal
        snap.detection = ["candidates_rules": masked / 2, "candidates_model": masked * 3,
                          "after_refinement": Int(Double(masked) * 1.25), "after_allowlist": Int(Double(masked) * 1.08),
                          "masked": masked]
        snap.scanMs = .init(p50: 21, p95: 88, n: 400)
        snap.vaultSize = 37
        for i in 0..<14 { snap.recent.append(event(at: now - Double(14 - i) * 7)) }
    }

    private func event(at ts: Double) -> Snapshot.Event {
        let types = ["SECRET", "SECRET", "EMAIL", "PERSON", "PHONE"]
        var redacted: [String: Int] = [:]
        if Int.random(in: 0..<10) < 4 { redacted[types.randomElement()!] = Int.random(in: 1...3) }
        let blocked = Int.random(in: 0..<40) == 0
        return .init(ts: ts, path: "/v1/messages", outcome: blocked ? "blocked" : "forwarded", status: blocked ? 500 : 200,
                     scanMs: blocked ? nil : Double.random(in: 6...120), redacted: redacted,
                     restored: redacted.isEmpty || Bool.random() ? [:] : ["SECRET": 1])
    }

    mutating func next() -> Snapshot {
        tick += 1
        let now = Date().timeIntervalSince1970
        snap.uptimeS = now - snap.started
        if tick % 2 == 0 {
            let e = event(at: now)
            snap.recent.append(e)
            if snap.recent.count > 200 { snap.recent.removeFirst() }
            snap.funnel.requests += 1
            snap.requests[e.outcome, default: 0] += 1
            if e.scanMs != nil { snap.funnel.scanned += 1 }
            if !e.redacted.isEmpty { snap.funnel.withFindings += 1 }
            for (k, v) in e.redacted {
                snap.redacted[k, default: 0] += v; snap.funnel.masked += v
                snap.detection["masked", default: 0] += v
                snap.detection["after_allowlist", default: 0] += v
                snap.detection["after_refinement", default: 0] += v + 1
                snap.detection["candidates_model", default: 0] += v * 3
            }
            for (k, v) in e.restored { snap.restored[k, default: 0] += v; snap.funnel.restored += v }
            if var last = snap.timeline.last {
                for (k, v) in e.redacted { last.masked[k, default: 0] += v }
                last.requests += 1
                snap.timeline[snap.timeline.count - 1] = last
            }
        }
        return snap
    }
}
