import SwiftUI

/// One value sotto masked in new text (`GET /_sotto/findings`). Never the value: its type, the
/// rule that found it, its length, and for values of 8 or more characters the first and last one.
struct Finding: Decodable, Sendable, Identifiable {
    var ts: Double
    var seq: Int
    var type: String
    /// rules, model, user (your own rule) or known (masked earlier in the conversation).
    var detector: String
    var rule: String
    var chars: Int
    /// `g…w`, `•••` for short values, nil with [log] previews = false.
    var preview: String?
    /// masked, or observed (observe mode: sent unmasked).
    var outcome: String
    var client: String?
    var provider: String?

    var id: String { "\(ts)-\(seq)" }
    var date: Date { Date(timeIntervalSince1970: ts) }

    var foundBy: String {
        switch detector {
        case "rules": rule
        case "user": "your rule: \(rule)"
        case "known": "seen earlier"
        default: "local model"
        }
    }

    var clientName: String {
        switch client ?? "claude-code" {
        case "claude-code": "Claude Code"
        case "codex": "Codex"
        case let other: other
        }
    }

    func matches(_ query: String) -> Bool {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        if q.isEmpty { return true }
        return [preview ?? "", type, Theme.label(type), foundBy, clientName, outcome].contains { $0.lowercased().contains(q) }
    }

    /// Synthetic rows for preview mode, clearly not real values.
    static let samples: [Finding] = {
        let now = Date().timeIntervalSince1970
        let rows: [(String, String, String, String?, Int, String)] = [
            ("SECRET", "rules", "github-token", "g…Q", 40, "claude-code"), ("EMAIL", "rules", "email", "j…m", 21, "claude-code"),
            ("SECRET", "model", "", "W…7", 16, "claude-code"), ("PERSON", "model", "", "P…n", 11, "codex"),
            ("SECRET", "rules", "secret-assignment", "x…!", 18, "codex"), ("ACCOUNT", "user", "Employee ID", "•••", 6, "claude-code"),
            ("SECRET", "rules", "openai-project-key", "s…A", 164, "pi"), ("PHONE", "rules", "phone-nanp", "(…1", 14, "claude-code"),
            ("SECRET", "known", "", "g…Q", 40, "claude-code"), ("SECRET", "rules", "connection-string-password", "Z…k", 12, "opencode"),
            ("ADDRESS", "model", "", "4…1", 38, "claude-code"), ("SECRET", "rules", "aws-access-key-id", "A…V", 20, "codex"),
            ("DATE", "rules", "date-of-birth", "1…2", 10, "claude-code"), ("SECRET", "rules", "key-in-prose", "3…a", 32, "claude-code"),
        ]
        return rows.enumerated().map { i, r in
            Finding(ts: now - Double(i * 47 + 12), seq: 0, type: r.0, detector: r.1, rule: r.2, chars: r.4, preview: r.3,
                    outcome: i == 4 ? "observed" : "masked", client: r.5, provider: r.5 == "codex" ? "openai" : "anthropic")
        }
    }()
}

/// Logs: every value sotto masked in new text, newest first, searchable. Kept in sotto's memory
/// only, so the list starts empty after sotto restarts.
struct LogsPage: View {
    var store: StatsStore
    @State private var query = ""
    @State private var type = "ALL"
    @Environment(\.isSnapshot) private var isSnapshot

    var body: some View {
        let all = store.sampleMode ? Finding.samples : store.findings
        let shown = all.filter { (type == "ALL" || $0.type == type) && $0.matches(query) }
        VStack(spacing: 16) {
            PageHeader(title: "Logs", subtitle: "What sotto masked in new text, newest first. Only the first and last character of a value, kept in memory until sotto exits.") {
                PreviewToggle(store: store)
            }
            Card(title: "Masked values", subtitle: all.isEmpty ? "Nothing masked since sotto started" : "\(shown.count) of \(all.count)") {
                HStack(spacing: 8) {
                    search
                    typePicker
                }
            } content: {
                VStack(spacing: 0) {
                    if !store.previewsOn {
                        Text("Previews are off ([log] previews = false): types and rules only.")
                            .font(.system(size: 11.5)).foregroundStyle(Theme.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(.bottom, 8)
                    }
                    header
                    Rectangle().fill(Theme.border).frame(height: 1)
                    if isSnapshot {
                        ForEach(shown.prefix(14)) { row($0) }
                    } else {
                        ScrollView { LazyVStack(spacing: 0) { ForEach(shown) { row($0) } } }
                    }
                    if shown.isEmpty {
                        Text(all.isEmpty ? "Nothing yet. Values masked in new text appear here; the list starts empty each time sotto starts."
                                         : "No match")
                            .font(.system(size: 12)).foregroundStyle(Theme.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 12)
                    }
                    Spacer(minLength: 0)
                }
            }
        }
        .task(id: store.sampleMode) {
            while !Task.isCancelled {
                await store.loadFindings()
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    private var search: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass").font(.system(size: 11)).foregroundStyle(Theme.secondary)
            if isSnapshot {
                Text("Search").font(.system(size: 12)).foregroundStyle(Theme.secondary)
            } else {
                TextField("Search", text: $query, prompt: Text("Search: g…w, email, github-token, Codex"))
                    .textFieldStyle(.plain).font(.system(size: 12))
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 9).frame(width: 260, height: 26)
        .background(RoundedRectangle(cornerRadius: 7, style: .continuous).fill(Theme.faint))
    }

    @ViewBuilder private var typePicker: some View {
        if isSnapshot {
            Text("All types").font(.system(size: 12)).foregroundStyle(Theme.secondary)
                .padding(.horizontal, 9).frame(height: 26)
                .background(RoundedRectangle(cornerRadius: 7, style: .continuous).fill(Theme.faint))
        } else {
            Picker("Type", selection: $type) {
                Text("All types").tag("ALL")
                ForEach(Theme.typeOrder, id: \.self) { Text(Theme.label($0)).tag($0) }
            }
            .labelsHidden().frame(width: 130)
        }
    }

    private var header: some View {
        HStack(spacing: 12) {
            Text("Time").frame(width: 70, alignment: .leading)
            Text("Agent").frame(width: 92, alignment: .leading)
            Text("Type").frame(width: 110, alignment: .leading)
            Text("Value").frame(width: 70, alignment: .leading)
            Text("Length").frame(width: 56, alignment: .trailing)
            Text("Found by").frame(maxWidth: .infinity, alignment: .leading).padding(.leading, 8)
            Text("Outcome").frame(width: 80, alignment: .leading)
        }
        .font(.system(size: 11, weight: .medium)).foregroundStyle(Theme.secondary).padding(.bottom, 6)
    }

    private func row(_ f: Finding) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Text(f.date, format: .dateTime.hour().minute().second())
                    .font(.system(size: 11.5, design: .monospaced)).foregroundStyle(Theme.secondary).frame(width: 70, alignment: .leading)
                HStack(spacing: 6) {
                    Circle().fill(clientColor(f.client ?? "claude-code")).frame(width: 7, height: 7)
                    Text(f.clientName).lineLimit(1)
                }
                .font(.system(size: 12)).foregroundStyle(Theme.text).frame(width: 92, alignment: .leading)
                HStack(spacing: 6) {
                    Image(systemName: Theme.icon(f.type)).font(.system(size: 11)).foregroundStyle(Theme.secondary).frame(width: 14)
                    Text(Theme.label(f.type))
                }
                .font(.system(size: 12)).foregroundStyle(Theme.text).frame(width: 110, alignment: .leading)
                Text(f.preview ?? "—").font(.system(size: 12.5, design: .monospaced)).foregroundStyle(Theme.accent)
                    .frame(width: 70, alignment: .leading)
                    .help(f.preview == "•••" ? "Shorter than 8 characters: nothing of it is shown" : "First and last character only")
                Text("\(f.chars)").font(.system(size: 12)).monospacedDigit().foregroundStyle(Theme.secondary)
                    .frame(width: 56, alignment: .trailing)
                Text(f.foundBy).font(.system(size: 12, design: f.detector == "rules" ? .monospaced : .default))
                    .foregroundStyle(f.detector == "known" ? Theme.secondary : Theme.text).lineLimit(1).truncationMode(.middle)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(.leading, 8)
                HStack(spacing: 5) {
                    Image(systemName: f.outcome == "observed" ? "eye" : "eye.slash")
                    Text(f.outcome == "observed" ? "Observed" : "Masked")
                }
                .font(.system(size: 11.5)).foregroundStyle(f.outcome == "observed" ? Theme.secondary : Theme.accent)
                .help(f.outcome == "observed" ? "Observe mode: sent unmasked, only counted" : "")
                .frame(width: 80, alignment: .leading)
            }
            .padding(.vertical, 7)
            Rectangle().fill(Theme.border).frame(height: 1)
        }
    }
}
