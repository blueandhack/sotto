import SwiftUI

enum FlowGeometry {
    /// How long a pulse takes to cross a diagram, and how long after a request its reply sets off.
    static let lifetime: TimeInterval = 2.4
    static let replyDelay: TimeInterval = 1.2
}

/// The live flow as two Sankey diagrams on shared columns.
///
///   Requests out:   clients ─▶ sotto scans ─▶ clean / masked / observed / blocked ┆─▶ providers
///   Replies back:   clients ◀─ sotto restores (values put back / nothing to) ◀─┆── providers
///
/// Band width is the number of requests in the window. Each live request sends a dot along its
/// route: the dot takes each band's color, so it visibly changes at sotto.
struct FlowBandsView: View {
    var flows: Flows
    var pulses: [Pulse]
    var live: Bool

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 30, paused: !live || pulses.isEmpty)) { tl in
            Canvas { context, size in
                FlowBands(flows: flows, size: size).draw(&context, now: tl.date, pulses: pulses)
            }
        }
    }
}

// MARK: - Layout

/// A Sankey layout: nodes in columns, links between them, band thickness from the values.
struct BandLayout {
    struct Node {
        var id: String
        var col: Int
        var color: Color
        var rect: CGRect = .zero
    }
    struct Link {
        var from: String
        var to: String
        var value: Int
        var color: Color
        var t: CGFloat = 0     // thickness
        var y0: CGFloat = 0    // top of the band at its source
        var y1: CGFloat = 0    // top of the band at its target
    }

    var nodes: [String: Node] = [:]
    var links: [Link] = []

    static let bar: CGFloat = 8

    init(nodes order: [Node], links: [Link], xs: [CGFloat], top: CGFloat, height: CGFloat, gap: CGFloat = 12) {
        var inSum = [String: Int](), outSum = [String: Int]()
        for l in links where l.value > 0 {
            outSum[l.from, default: 0] += l.value
            inSum[l.to, default: 0] += l.value
        }
        let present = order.filter { max(inSum[$0.id] ?? 0, outSum[$0.id] ?? 0) > 0 }
        let byCol = Dictionary(grouping: present, by: \.col)
        // One scale for both sides of every node: the fullest column fills the height.
        var scale = CGFloat.greatestFiniteMagnitude
        for (_, col) in byCol {
            let total = col.reduce(0) { $0 + max(inSum[$1.id] ?? 0, outSum[$1.id] ?? 0) }
            let room = height - gap * CGFloat(max(col.count - 1, 0))
            if total > 0 { scale = min(scale, room / CGFloat(total)) }
        }
        if scale == .greatestFiniteMagnitude { scale = 0 }
        func thick(_ v: Int) -> CGFloat { v > 0 ? max(CGFloat(v) * scale, 1.5) : 0 }

        var links = links.filter { $0.value > 0 }
        for i in links.indices { links[i].t = thick(links[i].value) }
        var nodes = [String: Node]()
        for (c, col) in byCol {
            var y = top
            for var n in col {
                let h = max(links.filter { $0.to == n.id }.reduce(0) { $0 + $1.t },
                            links.filter { $0.from == n.id }.reduce(0) { $0 + $1.t }, 2)
                n.rect = CGRect(x: xs[c], y: y, width: Self.bar, height: h)
                nodes[n.id] = n
                y += h + gap
            }
        }
        // Stack each node's bands in the order of the nodes at their other end: fewest crossings.
        for (id, node) in nodes {
            var y = node.rect.minY
            for i in links.indices.filter({ links[$0].from == id }).sorted(by: { nodes[links[$0].to]!.rect.minY < nodes[links[$1].to]!.rect.minY }) {
                links[i].y0 = y
                y += links[i].t
            }
            y = node.rect.minY
            for i in links.indices.filter({ links[$0].to == id }).sorted(by: { nodes[links[$0].from]!.rect.minY < nodes[links[$1].from]!.rect.minY }) {
                links[i].y1 = y
                y += links[i].t
            }
        }
        self.nodes = nodes
        self.links = links
    }

    /// Band ends: the side of each bar that faces the other.
    func ends(_ l: Link) -> (CGFloat, CGFloat) {
        let s = nodes[l.from]!.rect, d = nodes[l.to]!.rect
        return d.minX > s.minX ? (s.maxX, d.minX) : (s.minX, d.maxX)
    }

    func band(_ l: Link) -> Path {
        let (x0, x1) = ends(l)
        let xm = (x0 + x1) / 2
        var p = Path()
        p.move(to: CGPoint(x: x0, y: l.y0))
        p.addCurve(to: CGPoint(x: x1, y: l.y1), control1: CGPoint(x: xm, y: l.y0), control2: CGPoint(x: xm, y: l.y1))
        p.addLine(to: CGPoint(x: x1, y: l.y1 + l.t))
        p.addCurve(to: CGPoint(x: x0, y: l.y0 + l.t), control1: CGPoint(x: xm, y: l.y1 + l.t), control2: CGPoint(x: xm, y: l.y0 + l.t))
        p.closeSubpath()
        return p
    }

    /// A point on a band's centre line, f from 0 (source) to 1 (target).
    func point(_ l: Link, _ f: CGFloat) -> CGPoint {
        let (x0, x1) = ends(l)
        let xm = (x0 + x1) / 2, a = l.y0 + l.t / 2, b = l.y1 + l.t / 2
        let u = 1 - f
        let x = u * u * u * x0 + 3 * u * u * f * xm + 3 * u * f * f * xm + f * f * f * x1
        let y = u * u * u * a + 3 * u * u * f * a + 3 * u * f * f * b + f * f * f * b
        return CGPoint(x: x, y: y)
    }

    func link(_ from: String, _ to: String) -> Link? { links.first { $0.from == from && $0.to == to } }
}

// MARK: - The two diagrams

private struct FlowBands {
    let flows: Flows
    let size: CGSize
    let out: BandLayout
    let back: BandLayout
    let xs: [CGFloat]
    let outTop: CGFloat, backTop: CGFloat, dashX: CGFloat

    static let results = ["clean", "masked", "observed", "failed", "blocked"]

    init(flows: Flows, size: CGSize) {
        self.flows = flows
        self.size = size
        let left: CGFloat = 132, right: CGFloat = size.width - 132
        let span = right - left
        xs = [left, left + span * 0.30, left + span * 0.58, right]
        dashX = (xs[2] + xs[3]) / 2 + 20
        let header: CGFloat = 26, gapBetween: CGFloat = 30
        let half = (size.height - 2 * header - gapBetween) / 2
        outTop = header
        backTop = header + half + gapBetween + header

        let clients = flows.clients.map(\.id)
        var providers = flows.providers.map(\.id)
        for o in flows.out { if let p = o.provider, !providers.contains(p) { providers.append(p) } }

        // Requests out.
        var nodes = clients.map { BandLayout.Node(id: "c:" + $0, col: 0, color: Self.clientColor($0)) }
        nodes.append(.init(id: "sotto", col: 1, color: Theme.text))
        nodes += Self.results.map { BandLayout.Node(id: "r:" + $0, col: 2, color: Self.resultColor($0)) }
        nodes += providers.map { BandLayout.Node(id: "p:" + $0, col: 3, color: Self.providerColor($0)) }
        var links: [BandLayout.Link] = []
        for c in flows.clients {
            links.append(.init(from: "c:" + c.id, to: "sotto", value: c.sent, color: Self.clientColor(c.id)))
        }
        for r in Self.results {
            let n = flows.out.filter { $0.kind == r }.reduce(0) { $0 + $1.n }
            links.append(.init(from: "sotto", to: "r:" + r, value: n, color: Self.resultColor(r)))
            for p in providers {
                let m = flows.out.filter { $0.kind == r && $0.provider == p }.reduce(0) { $0 + $1.n }
                links.append(.init(from: "r:" + r, to: "p:" + p, value: m, color: Self.resultColor(r)))
            }
        }
        out = BandLayout(nodes: nodes, links: links, xs: xs, top: outTop, height: half)

        // Replies back, right to left: providers, restore, clients.
        var bnodes = providers.map { BandLayout.Node(id: "p:" + $0, col: 3, color: Self.providerColor($0)) }
        bnodes += [BandLayout.Node(id: "restored", col: 1, color: Theme.success),
                   BandLayout.Node(id: "plain", col: 1, color: Self.resultColor("clean"))]
        bnodes += clients.map { BandLayout.Node(id: "c:" + $0, col: 0, color: Self.clientColor($0)) }
        var blinks: [BandLayout.Link] = []
        for p in providers {
            for (node, r) in [("restored", true), ("plain", false)] {
                let n = flows.back.filter { $0.provider == p && $0.restored == r }.reduce(0) { $0 + $1.n }
                blinks.append(.init(from: "p:" + p, to: node, value: n, color: r ? Theme.success : Self.resultColor("clean")))
            }
        }
        for c in clients {
            for (node, r) in [("restored", true), ("plain", false)] {
                let n = flows.back.filter { $0.client == c && $0.restored == r }.reduce(0) { $0 + $1.n }
                blinks.append(.init(from: node, to: "c:" + c, value: n, color: r ? Theme.success : Self.resultColor("clean")))
            }
        }
        back = BandLayout(nodes: bnodes, links: blinks, xs: xs, top: backTop, height: half)
    }

    // MARK: Colors

    static func clientColor(_ id: String) -> Color {
        switch id {
        case "claude-code": Color(light: NSColor(hex: 0xC8775A), dark: NSColor(hex: 0xD98B6E))
        case "codex": Color(light: NSColor(hex: 0x5B6270), dark: NSColor(hex: 0x9AA1AE))
        case "pi": Color(light: NSColor(hex: 0x6E78E0), dark: NSColor(hex: 0x8F98F0))
        default: Color(light: NSColor(hex: 0x2A9D8F), dark: NSColor(hex: 0x4FC3B5))
        }
    }

    static func providerColor(_ id: String) -> Color {
        switch id {
        case "anthropic": clientColor("claude-code")
        case "openai": clientColor("codex")
        default: clientColor("other")
        }
    }

    static func resultColor(_ kind: String) -> Color {
        switch kind {
        case "masked": Theme.accent
        case "observed": Color(light: NSColor(hex: 0xD97706), dark: NSColor(hex: 0xF59E0B))
        case "blocked": Theme.danger
        case "failed": Theme.secondary
        default: Color(light: NSColor(hex: 0xA6AEBB), dark: NSColor(hex: 0x5D6573))
        }
    }

    // MARK: Drawing

    func draw(_ ctx: inout GraphicsContext, now: Date, pulses: [Pulse]) {
        if flows.clients.isEmpty {
            ctx.draw(Text("No requests in this window yet").font(.system(size: 13)).foregroundStyle(Theme.secondary),
                     at: CGPoint(x: size.width / 2, y: size.height / 2))
            return
        }
        // The line between this Mac and the internet runs through both diagrams.
        var dash = Path()
        dash.move(to: CGPoint(x: dashX, y: outTop - 8))
        dash.addLine(to: CGPoint(x: dashX, y: size.height))
        ctx.stroke(dash, with: .color(Theme.secondary.opacity(0.5)), style: StrokeStyle(lineWidth: 1, dash: [4, 5]))
        var rule = Path()
        rule.move(to: CGPoint(x: 0, y: backTop - 44))
        rule.addLine(to: CGPoint(x: size.width, y: backTop - 44))
        ctx.stroke(rule, with: .color(Theme.border), lineWidth: 1)

        for layout in [out, back] {
            for l in layout.links { ctx.fill(layout.band(l), with: .color(l.color.opacity(0.28))) }
            for (_, n) in layout.nodes { ctx.fill(Path(roundedRect: n.rect, cornerRadius: 3), with: .color(n.color)) }
        }
        headers(&ctx)
        labels(&ctx)
        drawPulses(&ctx, now: now, pulses: pulses)
    }

    private func headers(_ ctx: inout GraphicsContext) {
        func h(_ s: String, _ x: CGFloat, _ y: CGFloat, _ anchor: UnitPoint) {
            ctx.draw(Text(s.uppercased()).font(.system(size: 10, weight: .semibold)).kerning(0.4).foregroundStyle(Theme.secondary),
                     at: CGPoint(x: x, y: y), anchor: anchor)
        }
        for (top, a, b, c, d) in [(outTop, "Requests out →", "sotto scans", "Result", "leaves this Mac"),
                                  (backTop, "← Replies back", "sotto restores", "", "arrives on this Mac")] {
            let y = top - 14
            h(a, xs[0] - 10, y, .trailing)
            h(b, xs[1] + 4, y, .center)
            if !c.isEmpty { h(c, xs[2], y, .leading) }
            h(d, dashX + 8, y, .leading)
        }
        if flows.unresolved > 0 {
            ctx.draw(Text("\(flows.unresolved) placeholders could not be restored").font(.system(size: 11, weight: .semibold))
                .foregroundStyle(Theme.danger), at: CGPoint(x: size.width, y: backTop - 14), anchor: .trailing)
        }
    }

    private func labels(_ ctx: inout GraphicsContext) {
        let pname = Dictionary(uniqueKeysWithValues: flows.providers.map { ($0.id, $0.name) })
        func sum(_ xs: [Int]) -> Int { xs.reduce(0, +) }

        // (node rect, title, detail, title color) per column, then placed without overlaps.
        typealias L = (CGRect, String, String, Color)
        var leftOut: [L] = [], leftBack: [L] = [], mid: [L] = [], rightOut: [L] = [], rightBack: [L] = [], restore: [L] = []
        for c in flows.clients {
            if let n = out.nodes["c:" + c.id] { leftOut.append((n.rect, c.name, c.sent.compact, Theme.text)) }
            if let n = back.nodes["c:" + c.id] {
                let got = sum(flows.back.filter { $0.client == c.id }.map(\.n))
                let values = sum(flows.back.filter { $0.client == c.id }.map(\.values))
                leftBack.append((n.rect, c.name, values > 0 ? "\(got.compact) · \(values.compact) restored" : got.compact, Theme.text))
            }
        }
        let detail = ["clean": "sent as is", "masked": "as placeholders", "observed": "sent unmasked", "failed": "upstream failed",
                      "blocked": "never sent"]
        let title = ["clean": "Clean", "masked": "Masked", "observed": "Observed", "failed": "Failed", "blocked": "Blocked"]
        let tint: [String: Color] = ["masked": Theme.accent, "blocked": Theme.danger, "observed": Self.resultColor("observed")]
        for r in Self.results {
            guard let n = out.nodes["r:" + r] else { continue }
            let v = sum(flows.out.filter { $0.kind == r }.map(\.n))
            mid.append((n.rect, "\(title[r]!) \(v.compact)", detail[r]!, tint[r] ?? Theme.text))
        }
        for (id, n) in out.nodes where id.hasPrefix("p:") {
            let p = String(id.dropFirst(2))
            rightOut.append((n.rect, pname[p] ?? p, "\(sum(flows.out.filter { $0.provider == p }.map(\.n)).compact) sent", Theme.text))
        }
        for (id, n) in back.nodes where id.hasPrefix("p:") {
            let p = String(id.dropFirst(2))
            rightBack.append((n.rect, pname[p] ?? p, "\(sum(flows.back.filter { $0.provider == p }.map(\.n)).compact) replies", Theme.text))
        }
        if let n = back.nodes["restored"] {
            let replies = sum(flows.back.filter(\.restored).map(\.n)), values = sum(flows.back.map(\.values))
            restore.append((n.rect, "Real values put back", "\(replies.compact) replies · \(values.compact) values", Theme.success))
        }
        if let n = back.nodes["plain"] {
            restore.append((n.rect, "Nothing to put back", "\(sum(flows.back.filter { !$0.restored }.map(\.n)).compact) replies", Theme.text))
        }

        func place(_ items: [L], x: CGFloat, anchor: UnitPoint) {
            var lastY = -CGFloat.infinity
            for (rect, t, d, color) in items.sorted(by: { $0.0.midY < $1.0.midY }) {
                let y = max(rect.midY - 8, lastY + 30)
                lastY = y
                ctx.draw(Text(t).font(.system(size: 12, weight: .semibold)).foregroundStyle(color), at: CGPoint(x: x, y: y), anchor: anchor)
                ctx.draw(Text(d).font(.system(size: 11)).foregroundStyle(Theme.secondary), at: CGPoint(x: x, y: y + 14), anchor: anchor)
            }
        }
        place(leftOut, x: xs[0] - 10, anchor: .trailing)
        place(leftBack, x: xs[0] - 10, anchor: .trailing)
        place(mid, x: xs[2] + BandLayout.bar + 8, anchor: .leading)
        place(restore, x: xs[1] + BandLayout.bar + 8, anchor: .leading)
        place(rightOut, x: xs[3] + BandLayout.bar + 8, anchor: .leading)
        place(rightBack, x: xs[3] + BandLayout.bar + 8, anchor: .leading)
    }

    private func drawPulses(_ ctx: inout GraphicsContext, now: Date, pulses: [Pulse]) {
        for pulse in pulses {
            let age = now.timeIntervalSince(pulse.born)
            guard age >= 0, age < FlowGeometry.lifetime else { continue }
            let (layout, route): (BandLayout, [(String, String)]) = switch pulse.kind {
            case .out(let r):
                (out, [("c:" + pulse.client, "sotto"), ("sotto", "r:" + r)] + (r == "blocked" || r == "failed" ? [] : [("r:" + r, "p:" + pulse.provider)]))
            case .back(let restored):
                (back, [("p:" + pulse.provider, restored ? "restored" : "plain"), (restored ? "restored" : "plain", "c:" + pulse.client)])
            }
            let links = route.compactMap { layout.link($0.0, $0.1) }
            guard links.count == route.count, !links.isEmpty else { continue }
            let progress = CGFloat(age / FlowGeometry.lifetime) * CGFloat(links.count)
            let i = min(Int(progress), links.count - 1)
            let p = layout.point(links[i], min(progress - CGFloat(i), 1))
            let fade = min(1, (FlowGeometry.lifetime - age) / 0.3)
            ctx.fill(Path(ellipseIn: CGRect(x: p.x - 7, y: p.y - 7, width: 14, height: 14)), with: .color(links[i].color.opacity(0.18 * fade)))
            ctx.fill(Path(ellipseIn: CGRect(x: p.x - 3.5, y: p.y - 3.5, width: 7, height: 7)), with: .color(links[i].color.opacity(fade)))
        }
    }
}
