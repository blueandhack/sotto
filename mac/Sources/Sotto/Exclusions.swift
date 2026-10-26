import AppKit
import SwiftUI

/// Projects where Claude Code skips sotto and goes straight to the API (`sotto exclude`).
struct ExclusionsCard: View {
    var engine: Engine

    var body: some View {
        Card(title: "Excluded projects", subtitle: "Claude Code in these goes straight to the API, unscanned") {
            PillButton(title: "Exclude a project…", icon: "plus") { pick() }
                .disabled(!engine.isBundled || engine.busy)
        } content: {
            let list = engine.status?.excluded ?? []
            VStack(alignment: .leading, spacing: 0) {
                if list.isEmpty {
                    Text("None. Every project goes through sotto.").font(.system(size: 12)).foregroundStyle(Theme.secondary)
                }
                ForEach(list) { p in
                    HStack(spacing: 10) {
                        Image(systemName: "folder").foregroundStyle(Theme.secondary)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(display(p.path)).font(.system(size: 12, design: .monospaced)).foregroundStyle(Theme.text)
                                .lineLimit(1).truncationMode(.middle)
                            Text(p.active ? "→ \(p.url)" : "setting removed by hand: goes through sotto")
                                .font(.system(size: 11)).foregroundStyle(Theme.secondary).lineLimit(1)
                        }
                        Spacer(minLength: 8)
                        PillButton(title: "Include") { Task { await engine.include(p.path) } }
                    }
                    .padding(.vertical, 7)
                }
                if let note = engine.exclusionNote {
                    Text(note).font(.system(size: 11.5)).foregroundStyle(Theme.secondary).padding(.top, 6)
                }
            }
        }
    }

    private func display(_ path: String) -> String {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        return path.hasPrefix(home) ? "~" + path.dropFirst(home.count) : path
    }

    private func pick() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.prompt = "Exclude"
        panel.message = "Claude Code in this project (its git repository) will skip sotto and send everything to the API unscanned."
        if panel.runModal() == .OK, let url = panel.url {
            Task { await engine.exclude(url) }
        }
    }
}
