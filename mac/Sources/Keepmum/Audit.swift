import AppKit
import SwiftUI

/// Audit: whether keepmum's tamper-evident log is intact, and every change to its protection,
/// newest first, with the ones that turned protection down marked. Requests are in the log too
/// (`keepmum audit list`); this page shows the rest. Counts and names only, never values.
struct AuditPage: View {
    var engine: Engine
    @State private var onlyWeakening = false
    @Environment(\.isSnapshot) private var isSnapshot

    var body: some View {
        let shown = engine.audit.filter { !onlyWeakening || $0.weakens }
        VStack(spacing: 16) {
            PageHeader(title: "Audit", subtitle: "A record keepmum cannot quietly change: every setting that turned protection down, and when keepmum ran.") {
                EmptyView()
            }
            chain
            Card(title: "Changes and coverage", subtitle: engine.audit.isEmpty ? "Nothing recorded yet" : "\(shown.count) of \(engine.audit.count), newest first") {
                PillButton(title: onlyWeakening ? "Show everything" : "Only what weakened protection",
                           icon: onlyWeakening ? "line.3.horizontal" : "exclamationmark.shield") { onlyWeakening.toggle() }
            } content: {
                VStack(spacing: 0) {
                    if isSnapshot {
                        ForEach(shown.prefix(9)) { row($0) }
                    } else {
                        ScrollView { LazyVStack(spacing: 0) { ForEach(shown) { row($0) } } }
                    }
                    if shown.isEmpty {
                        Text(engine.audit.isEmpty ? "Changes to keepmum's settings, protection and exclusions appear here, with each start and stop of the service."
                                                  : "Nothing weakened protection in this period.")
                            .font(.system(size: 12)).foregroundStyle(Theme.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 12)
                    }
                    Spacer(minLength: 0)
                }
            }
        }
        .task {
            while !Task.isCancelled {
                await engine.loadAudit()
                try? await Task.sleep(for: .seconds(15))
            }
        }
    }

    /// The chain check: intact, or the problems `keepmum audit verify` found.
    @ViewBuilder private var chain: some View {
        let check = engine.auditCheck
        let ok = check?.ok ?? true
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: check == nil ? "seal" : ok ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                .font(.system(size: 22)).foregroundStyle(check == nil ? Theme.secondary : ok ? Theme.success : Theme.danger)
            VStack(alignment: .leading, spacing: 4) {
                Text(check == nil ? "Not checked yet" : ok ? "Log intact" : "Log changed outside keepmum")
                    .font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.text)
                if let check, ok {
                    Text("\(check.entries.formatted()) entries chain together, and the log still holds what it held at the last check.")
                        .font(.system(size: 12)).foregroundStyle(Theme.secondary)
                } else if let check {
                    ForEach(check.problems.prefix(4), id: \.self) { p in
                        Text(p).font(.system(size: 12)).foregroundStyle(Theme.text)
                    }
                    Text("Run `keepmum audit verify` for the full list.").font(.system(size: 11.5)).foregroundStyle(Theme.secondary)
                } else {
                    Text("The Audit page checks the log each time it opens.").font(.system(size: 12)).foregroundStyle(Theme.secondary)
                }
            }
            Spacer()
            if let last = check?.last {
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Head").font(.system(size: 11, weight: .medium)).foregroundStyle(Theme.secondary)
                    Text(verbatim: "\(last.seq):\(last.hash.prefix(16))").font(.system(size: 12, design: .monospaced)).foregroundStyle(Theme.text)
                        .textSelection(.enabled)
                    PillButton(title: "Copy head", icon: "doc.on.doc") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString("\(last.seq):\(last.hash)", forType: .string)
                    }
                    .help("Keep it outside this Mac; `keepmum audit verify --anchor` then shows whether the log was rewritten since")
                }
            }
        }
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(ok ? Theme.surface : Theme.danger.opacity(0.08)))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(ok ? Theme.border : Theme.danger.opacity(0.3)))
    }

    private func row(_ e: Engine.AuditEntry) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Text(e.date, format: .dateTime.month(.abbreviated).day().hour().minute())
                    .font(.system(size: 11.5, design: .monospaced)).foregroundStyle(Theme.secondary).frame(width: 110, alignment: .leading)
                HStack(spacing: 6) {
                    Image(systemName: icon(e.event)).font(.system(size: 11)).frame(width: 14)
                    Text(label(e.event))
                }
                .font(.system(size: 12)).foregroundStyle(Theme.text).frame(width: 110, alignment: .leading)
                VStack(alignment: .leading, spacing: 2) {
                    Text(e.summary).font(.system(size: 12)).foregroundStyle(Theme.text).lineLimit(2)
                    if let by = e.by {
                        Text(by).font(.system(size: 11)).foregroundStyle(Theme.secondary).lineLimit(1)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if e.weakens {
                    Text("Weakened").font(.system(size: 11, weight: .semibold)).foregroundStyle(Theme.danger)
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Capsule().fill(Theme.danger.opacity(0.1)))
                }
                Text(verbatim: "#\(e.seq)").font(.system(size: 11, design: .monospaced)).foregroundStyle(Theme.secondary)
                    .frame(width: 56, alignment: .trailing)
            }
            .padding(.vertical, 8)
            Rectangle().fill(Theme.border).frame(height: 1)
        }
    }

    private func label(_ event: String) -> String {
        switch event {
        case "config": "Settings"
        case "protect": "Protection"
        case "exclude": "Excluded"
        case "include": "Included"
        case "start": "Started"
        case "stop": "Stopped"
        case "pruned": "Retention"
        default: event.capitalized
        }
    }

    private func icon(_ event: String) -> String {
        switch event {
        case "config": "slider.horizontal.3"
        case "protect": "shield"
        case "exclude": "arrow.uturn.right"
        case "include": "arrow.uturn.left"
        case "start": "play.circle"
        case "stop": "stop.circle"
        case "pruned": "scissors"
        default: "circle"
        }
    }
}
