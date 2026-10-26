import SwiftUI

enum FlowGeometry {
    static let lifetime: TimeInterval = 2.8
}

/// The live flow as a map of where traffic goes, on two rounded regions: this Mac and
/// Anthropic. Only what crosses from one region to the other leaves the computer.
///
///   (Claude Code) ─▶ Scan ─┬─ clean ──────────────────────────▶ (Anthropic)
///                          ├─ sensitive ─▶ Mask ─ placeholders ─▶
///                          ╰─ blocked ─▶ Blocked (never sent)
///   (Claude Code) ◀─ restored ─ Restore ◀─ answers ────────────── (Anthropic)
///
/// Lane widths and particle density follow the real counts; each real event sends a bright
/// particle down its route and pings the nodes it passes.
struct PipelineView: View {
    var snapshot: Snapshot
    var pulses: [Pulse]
    var live: Bool
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 30, paused: !live || snapshot.contentRequests == 0)) { tl in
            Canvas { context, size in
                FlowMap(size: size, snapshot: snapshot).draw(&context, now: tl.date, pulses: pulses, animate: live)
            } symbols: {
                logo("claude", fallback: "terminal.fill").tag(0)
                symbol("doc.text.magnifyingglass", Theme.accent).tag(1)
                symbol("eye.slash", Theme.accent).tag(2)
                symbol("hand.raised.fill", Theme.danger).tag(3)
                logo(scheme == .dark ? "anthropic-dark" : "anthropic-light", fallback: "cloud.fill").tag(4)
                symbol("arrow.uturn.backward", Theme.success).tag(5)
                Image(systemName: Brand.thisMacSymbol).font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.secondary).tag(6)
                Image(systemName: "cloud").font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.secondary).tag(7)
            }
        }
        .frame(height: 236)
    }

    private func symbol(_ name: String, _ color: Color) -> some View {
        Image(systemName: name).font(.system(size: 12, weight: .semibold)).foregroundStyle(color)
    }

    /// The service's logo (mac/Brand), or a symbol if the file is missing.
    @ViewBuilder private func logo(_ name: String, fallback: String) -> some View {
        if let image = Brand.logo(name) {
            Image(nsImage: image).resizable().interpolation(.high).scaledToFit().frame(width: 26, height: 26)
        } else {
            Image(systemName: fallback).font(.system(size: 18, weight: .semibold)).foregroundStyle(Theme.accent)
        }
    }
}

/// A lane: a smooth path sampled into points, so particles move at a constant speed.
private struct Lane {
    private(set) var points: [CGPoint] = []
    private(set) var distances: [CGFloat] = [0]

    init(_ start: CGPoint, _ curves: [(to: CGPoint, c1: CGPoint, c2: CGPoint)]) {
        points = [start]
        var from = start
        for c in curves {
            for k in 1...28 {
                let t = CGFloat(k) / 28, u = 1 - t
                let p = CGPoint(x: u * u * u * from.x + 3 * u * u * t * c.c1.x + 3 * u * t * t * c.c2.x + t * t * t * c.to.x,
                                y: u * u * u * from.y + 3 * u * u * t * c.c1.y + 3 * u * t * t * c.c2.y + t * t * t * c.to.y)
                distances.append(distances.last! + hypot(p.x - points.last!.x, p.y - points.last!.y))
                points.append(p)
            }
            from = c.to
        }
    }

    /// A smooth S curve from a to b, leaving and arriving horizontally.
    static func s(_ a: CGPoint, _ b: CGPoint) -> Lane {
        let dx = (b.x - a.x) / 2
        return Lane(a, [(b, CGPoint(x: a.x + dx, y: a.y), CGPoint(x: b.x - dx, y: b.y))])
    }

    var length: CGFloat { distances.last ?? 0 }

    var path: Path {
        var p = Path()
        p.addLines(points)
        return p
    }

    func point(at distance: CGFloat) -> CGPoint {
        let d = min(max(distance, 0), length)
        var lo = 0, hi = distances.count - 1
        while hi - lo > 1 {
            let mid = (lo + hi) / 2
            if distances[mid] < d { lo = mid } else { hi = mid }
        }
        let span = max(distances[hi] - distances[lo], 0.0001)
        let f = (d - distances[lo]) / span
        return CGPoint(x: points[lo].x + (points[hi].x - points[lo].x) * f, y: points[lo].y + (points[hi].y - points[lo].y) * f)
    }
}

private struct Node {
    enum Shape { case pill, endpoint }
    var rect: CGRect
    var symbol: Int
    var title: String
    var detail: String
    var tint: Color
    var shape: Shape = .pill
    var center: CGPoint { CGPoint(x: rect.midX, y: rect.midY) }
}

private struct FlowMap {
    let size: CGSize
    let s: Snapshot
    let nodes: [String: Node]
    let lanes: [String: Lane]
    let boundaryX: CGFloat
    let yTop: CGFloat, yOut: CGFloat, yRet: CGFloat

    var clean: Int { max(s.funnel.scanned - s.funnel.withFindings, 0) }

    static let endpointRadius: CGFloat = 26

    init(size: CGSize, snapshot s: Snapshot) {
        self.size = size
        self.s = s
        let w = size.width, h = size.height
        let yTop: CGFloat = 44, yOut = h * 0.43, yRet = h * 0.84
        let yMid = (yOut + yRet) / 2
        self.yTop = yTop; self.yOut = yOut; self.yRet = yRet
        boundaryX = w * 0.76
        let r = Self.endpointRadius
        func pill(_ cx: CGFloat, _ cy: CGFloat) -> CGRect { CGRect(x: cx - 68, y: cy - 20, width: 136, height: 40) }
        func endpoint(_ cx: CGFloat) -> CGRect { CGRect(x: cx - r, y: yMid - r, width: 2 * r, height: 2 * r) }
        var n: [String: Node] = [:]
        n["claude"] = Node(rect: endpoint(64), symbol: 0, title: "Claude Code", detail: "\(s.contentRequests.compact) requests",
                           tint: Theme.accent, shape: .endpoint)
        n["anthropic"] = Node(rect: endpoint(w - 64), symbol: 4, title: "Anthropic API", detail: "\(s.funnel.scanned.compact) received",
                              tint: Theme.text, shape: .endpoint)
        n["scan"] = Node(rect: pill(w * 0.27, yOut), symbol: 1, title: "Scan", detail: "\(s.funnel.scanned.compact) scanned", tint: Theme.accent)
        n["mask"] = Node(rect: pill(w * 0.52, yOut), symbol: 2, title: "Mask", detail: "\((s.vaultSize ?? 0).compact) unique values", tint: Theme.accent)
        n["blocked"] = Node(rect: pill(w * 0.45, h * 0.64), symbol: 3, title: "Blocked", detail: "never sent", tint: Theme.danger)
        n["restore"] = Node(rect: pill(w * 0.52, yRet), symbol: 5, title: "Restore", detail: "\(s.restoredTotal.compact) values back", tint: Theme.success)
        nodes = n

        let claude = n["claude"]!.center, anth = n["anthropic"]!.center
        let scan = n["scan"]!.rect, mask = n["mask"]!.rect, blocked = n["blocked"]!.rect, restore = n["restore"]!.rect
        // Points on the endpoint circles, so lanes meet them at an angle, not a corner.
        func onCircle(_ c: CGPoint, degrees: CGFloat) -> CGPoint {
            CGPoint(x: c.x + r * cos(degrees * .pi / 180), y: c.y + r * sin(degrees * .pi / 180))
        }
        var l: [String: Lane] = [:]
        l["intake"] = .s(onCircle(claude, degrees: -35), CGPoint(x: scan.minX, y: yOut))
        let cleanEnd = onCircle(anth, degrees: -125)
        l["clean"] = Lane(CGPoint(x: scan.maxX - 6, y: yOut - 12), [
            (CGPoint(x: scan.maxX + 90, y: yTop), CGPoint(x: scan.maxX + 45, y: yOut - 12), CGPoint(x: scan.maxX + 45, y: yTop)),
            (CGPoint(x: cleanEnd.x - 110, y: yTop), CGPoint(x: scan.maxX + 200, y: yTop), CGPoint(x: cleanEnd.x - 200, y: yTop)),
            (cleanEnd, CGPoint(x: cleanEnd.x - 40, y: yTop), CGPoint(x: cleanEnd.x - 20, y: cleanEnd.y - 30)),
        ])
        l["sensitive"] = .s(CGPoint(x: scan.maxX, y: yOut), CGPoint(x: mask.minX, y: yOut))
        l["placeholders"] = .s(CGPoint(x: mask.maxX, y: yOut), onCircle(anth, degrees: -165))
        // Blocked: one smooth curve down from Scan into the Blocked node.
        let blockedStart = CGPoint(x: scan.midX, y: scan.maxY)
        l["blocked"] = Lane(blockedStart, [
            (CGPoint(x: blocked.minX, y: blocked.midY), CGPoint(x: blockedStart.x, y: blocked.midY), CGPoint(x: blockedStart.x + 10, y: blocked.midY)),
        ])
        l["answers"] = .s(onCircle(anth, degrees: 145), CGPoint(x: restore.maxX, y: yRet))
        l["restored"] = .s(CGPoint(x: restore.minX, y: yRet), onCircle(claude, degrees: 55))
        lanes = l
    }

    // MARK: Drawing

    func draw(_ context: inout GraphicsContext, now: Date, pulses: [Pulse], animate: Bool) {
        let total = max(s.contentRequests, 1)
        func width(_ v: Int) -> CGFloat { v > 0 ? 3 + 9 * sqrt(CGFloat(min(v, total)) / CGFloat(total)) : 1.5 }
        let volumes: [String: Int] = [
            "intake": s.contentRequests, "clean": clean, "sensitive": s.funnel.withFindings,
            "placeholders": s.funnel.withFindings, "blocked": s.blocked,
            "answers": s.funnel.scanned, "restored": s.restoredTotal,
        ]
        let colors: [String: Color] = [
            "intake": Theme.accent, "clean": Theme.accent, "sensitive": Theme.accent, "placeholders": Theme.placeholder,
            "blocked": Theme.danger, "answers": Theme.placeholder, "restored": Theme.success,
        ]

        // Two rounded regions: what stays on this Mac, and what reaches Anthropic.
        let mac = CGRect(x: 0, y: 0, width: boundaryX - 6, height: size.height)
        let cloud = CGRect(x: boundaryX + 6, y: 0, width: size.width - boundaryX - 6, height: size.height)
        for region in [mac, cloud] {
            context.fill(Path(roundedRect: region, cornerRadius: 22, style: .continuous), with: .color(Theme.faint))
        }
        regionLabel(&context, symbol: 6, "This Mac", at: CGPoint(x: mac.minX + 16, y: 16))
        regionLabel(&context, symbol: 7, "Anthropic", at: CGPoint(x: cloud.minX + 16, y: 16))

        for (name, lane) in lanes {
            let v = volumes[name] ?? 0
            context.stroke(lane.path, with: .color((colors[name] ?? Theme.accent).opacity(v > 0 ? 0.22 : 0.08)),
                           style: StrokeStyle(lineWidth: width(v), lineCap: .round, lineJoin: .round))
        }

        // A steady stream on every lane that carries traffic.
        let t = now.timeIntervalSinceReferenceDate
        let speed: CGFloat = 70  // points per second
        if s.contentRequests > 0 {
            for (name, lane) in lanes {
                let v = volumes[name] ?? 0
                guard v > 0, lane.length > 0 else { continue }
                let count = min(9, 2 + Int(log2(Double(v) + 1)))
                for i in 0..<count {
                    let base = (animate ? CGFloat(t) * speed : 0) / lane.length + CGFloat(i) / CGFloat(count)
                    let f = base.truncatingRemainder(dividingBy: 1)
                    var color = colors[name] ?? Theme.accent
                    if name == "blocked" { color = color.opacity(Double(f < 0.7 ? 1 : (1 - f) / 0.3)) }
                    dot(&context, lane.point(at: f * lane.length), color, 2.6, square: name == "placeholders" || name == "answers")
                }
            }
        }

        // Real events: a bright particle down the route each one took; nodes ping as it passes.
        var pings: [String: Double] = [:]
        for pulse in pulses {
            let age = now.timeIntervalSince(pulse.born) - Double(abs(pulse.id.hashValue) % 400) / 1000
            guard age >= 0, age < FlowGeometry.lifetime else { continue }
            let route: [String], stops: [String], color: Color
            var placeholderLanes: Set<Int> = []
            switch pulse.kind {
            case .clean: (route, stops, color) = (["intake", "clean"], ["claude", "scan", "anthropic"], Theme.accent)
            case .masked:
                (route, stops, color) = (["intake", "sensitive", "placeholders"], ["claude", "scan", "mask", "anthropic"], Theme.accent)
                placeholderLanes = [2]
            case .blocked: (route, stops, color) = (["intake", "blocked"], ["claude", "scan", "blocked"], Theme.danger)
            case .restored:
                (route, stops, color) = (["answers", "restored"], ["anthropic", "restore", "claude"], Theme.success)
                placeholderLanes = [0]
            }
            let segs = route.compactMap { lanes[$0] }
            let walked = CGFloat(age / FlowGeometry.lifetime) * segs.reduce(0) { $0 + $1.length }
            var d = walked, k = 0
            while k < segs.count - 1, d > segs[k].length { d -= segs[k].length; k += 1 }
            let square = placeholderLanes.contains(k)
            dot(&context, segs[k].point(at: d), square ? Theme.placeholder : color, 4.2, glow: true, square: square)
            var joint: CGFloat = 0
            for (j, stop) in stops.enumerated() {
                if abs(walked - joint) < 24 { pings[stop] = max(pings[stop] ?? 0, Double(1 - abs(walked - joint) / 24)) }
                if j < segs.count { joint += segs[j].length }
            }
        }

        for (key, node) in nodes { drawNode(&context, node, ping: pings[key] ?? 0) }

        // Lane labels, each on a small pill.
        let scan = nodes["scan"]!.rect
        let restore = nodes["restore"]!.rect, claude = nodes["claude"]!.rect, anth = nodes["anthropic"]!.rect
        pill(&context, "\(clean.compact) clean · sent as is", at: CGPoint(x: (scan.maxX + anth.minX) / 2, y: yTop))
        // Labels sit on their own lanes, so they never cover another node.
        pill(&context, "\(s.funnel.withFindings.compact) sensitive", at: lanes["sensitive"]!.point(at: lanes["sensitive"]!.length / 2))
        pill(&context, "placeholders only", at: lanes["placeholders"]!.point(at: lanes["placeholders"]!.length * 0.42))
        let b = lanes["blocked"]!.point(at: lanes["blocked"]!.length * 0.38)
        pill(&context, "\(s.blocked.compact) blocked", at: CGPoint(x: b.x - 38, y: b.y),
             color: s.blocked > 0 ? Theme.danger : Theme.secondary)
        pill(&context, "answers with placeholders", at: CGPoint(x: (restore.maxX + anth.minX) / 2 + 10, y: yRet + 22))
        pill(&context, "\(s.restoredTotal.compact) real values restored", at: CGPoint(x: (claude.maxX + restore.minX) / 2 + 10, y: yRet + 22),
             color: Theme.success)
    }

    private func drawNode(_ context: inout GraphicsContext, _ node: Node, ping: Double) {
        switch node.shape {
        case .endpoint:
            let c = node.center, r = Self.endpointRadius
            let halo = Path(ellipseIn: node.rect.insetBy(dx: -6 - 6 * CGFloat(1 - ping), dy: -6 - 6 * CGFloat(1 - ping)))
            if ping > 0 { context.stroke(halo, with: .color(Theme.accent.opacity(0.4 * ping)), lineWidth: 2) }
            // A neutral disc, so the service's own logo shows in its own colors.
            let disc = Path(ellipseIn: node.rect)
            context.fill(disc, with: .color(Theme.surface))
            context.stroke(disc, with: .color(Theme.border), lineWidth: 1.5)
            context.stroke(Path(ellipseIn: node.rect.insetBy(dx: 3, dy: 3)), with: .color(Theme.faint), lineWidth: 1)
            if let sym = context.resolveSymbol(id: node.symbol) { context.draw(sym, at: c) }
            text(&context, node.title, at: CGPoint(x: c.x, y: c.y - r - 14), size: 12, weight: .semibold, color: Theme.text, anchor: .center)
            text(&context, node.detail, at: CGPoint(x: c.x, y: c.y + r + 13), size: 10.5, color: Theme.secondary, anchor: .center)
        case .pill:
            let shape = Path(roundedRect: node.rect, cornerRadius: node.rect.height / 2, style: .continuous)
            context.fill(shape, with: .color(Theme.surface))
            context.stroke(shape, with: .color(node.tint.opacity(0.28 + 0.5 * ping)), lineWidth: 1 + 1.5 * ping)
            if ping > 0 {
                let r = node.rect.insetBy(dx: -3 - 4 * CGFloat(1 - ping), dy: -3 - 4 * CGFloat(1 - ping))
                context.stroke(Path(roundedRect: r, cornerRadius: r.height / 2, style: .continuous), with: .color(node.tint.opacity(0.4 * ping)), lineWidth: 2)
            }
            let badge = CGPoint(x: node.rect.minX + 20, y: node.rect.midY)
            context.fill(Path(ellipseIn: CGRect(x: badge.x - 14, y: badge.y - 14, width: 28, height: 28)), with: .color(node.tint.opacity(0.13)))
            if let sym = context.resolveSymbol(id: node.symbol) { context.draw(sym, at: badge) }
            text(&context, node.title, at: CGPoint(x: node.rect.minX + 42, y: node.rect.midY - 7), size: 12, weight: .semibold, color: Theme.text, anchor: .leading)
            text(&context, node.detail, at: CGPoint(x: node.rect.minX + 42, y: node.rect.midY + 8), size: 10.5, color: Theme.secondary, anchor: .leading)
        }
    }

    private func regionLabel(_ context: inout GraphicsContext, symbol: Int, _ title: String, at p: CGPoint) {
        if let sym = context.resolveSymbol(id: symbol) { context.draw(sym, at: CGPoint(x: p.x + 7, y: p.y), anchor: .center) }
        text(&context, title, at: CGPoint(x: p.x + 20, y: p.y), size: 11, weight: .semibold, color: Theme.secondary, anchor: .leading)
    }

    private func pill(_ context: inout GraphicsContext, _ string: String, at p: CGPoint, color: Color = Theme.secondary) {
        let resolved = context.resolve(Text(string).font(.system(size: 10.5, weight: .medium)).foregroundStyle(color))
        let m = resolved.measure(in: CGSize(width: 400, height: 30))
        let rect = CGRect(x: p.x - m.width / 2 - 8, y: p.y - m.height / 2 - 3, width: m.width + 16, height: m.height + 6)
        context.fill(Path(roundedRect: rect, cornerRadius: rect.height / 2), with: .color(Theme.surface))
        context.stroke(Path(roundedRect: rect, cornerRadius: rect.height / 2), with: .color(Theme.border), lineWidth: 1)
        context.draw(resolved, at: p, anchor: .center)
    }

    private func text(_ context: inout GraphicsContext, _ string: String, at p: CGPoint, size: CGFloat, weight: Font.Weight = .regular,
                      color: Color, anchor: UnitPoint) {
        context.draw(Text(string).font(.system(size: size, weight: weight)).foregroundStyle(color), at: p, anchor: anchor)
    }

    private func dot(_ context: inout GraphicsContext, _ p: CGPoint, _ color: Color, _ r: CGFloat, glow: Bool = false, square: Bool = false) {
        if glow {
            let g = Path(ellipseIn: CGRect(x: p.x - r * 3, y: p.y - r * 3, width: r * 6, height: r * 6))
            context.fill(g, with: .radialGradient(Gradient(colors: [color.opacity(0.35), .clear]), center: p, startRadius: 0, endRadius: r * 3))
        }
        let rect = CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2)
        context.fill(square ? Path(roundedRect: rect, cornerRadius: r * 0.5) : Path(ellipseIn: rect), with: .color(color))
    }
}
