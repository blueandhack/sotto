import SwiftUI

struct FunnelStage: Identifiable {
    var label: String
    var value: Int
    var color: Color
    var note: String? = nil
    var id: String { label }
}

/// A smooth funnel: each band narrows from its stage's value to the next one's. Widths use a
/// square-root scale so a stage that is 2% of the first is still readable.
struct FunnelView: View {
    var stages: [FunnelStage]
    var funnelFraction: CGFloat = 0.56

    var body: some View {
        GeometryReader { geo in
            let rowHeight = geo.size.height / CGFloat(max(stages.count, 1))
            let funnelWidth = geo.size.width * funnelFraction
            let top = Double(max(stages.first?.value ?? 1, 1))
            let widths = stages.map { s in max(0.10, sqrt(Double(max(s.value, 0)) / top)) }
            ZStack(alignment: .topLeading) {
                ForEach(Array(stages.enumerated()), id: \.element.id) { i, stage in
                    let w0 = CGFloat(widths[i]) * funnelWidth
                    let w1 = CGFloat(i + 1 < widths.count ? widths[i + 1] : widths[i] * 0.85) * funnelWidth
                    Band(top: w0, bottom: w1)
                        .fill(stage.color)
                        .frame(width: funnelWidth, height: rowHeight - 4)
                        .offset(y: CGFloat(i) * rowHeight)
                    Text(stage.value.compact)
                        .font(.system(size: 14, weight: .bold, design: .rounded)).monospacedDigit()
                        .foregroundStyle(Color.white)
                        .contentTransition(.numericText())
                        .frame(width: funnelWidth, height: rowHeight - 4)
                        .offset(y: CGFloat(i) * rowHeight)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(stage.label).font(.system(size: 12, weight: .medium)).foregroundStyle(Theme.text)
                            .lineLimit(1).minimumScaleFactor(0.75)
                        if i > 0, let prev = stages[i - 1].value as Int?, prev > 0 {
                            Text(stage.note ?? String(format: "%.0f%% of previous", Double(stage.value) / Double(prev) * 100))
                                .font(.system(size: 10.5)).foregroundStyle(Theme.secondary)
                        } else if let note = stage.note {
                            Text(note).font(.system(size: 10.5)).foregroundStyle(Theme.secondary)
                        }
                    }
                    .frame(width: max(geo.size.width - funnelWidth - 14, 0), height: rowHeight - 4, alignment: .leading)
                    .offset(x: funnelWidth + 14, y: CGFloat(i) * rowHeight)
                }
            }
            .animation(.spring(duration: 0.6), value: stages.map(\.value))
        }
    }
}

private struct Band: Shape {
    var top: CGFloat
    var bottom: CGFloat
    var animatableData: AnimatablePair<CGFloat, CGFloat> {
        get { AnimatablePair(top, bottom) }
        set { top = newValue.first; bottom = newValue.second }
    }

    func path(in rect: CGRect) -> Path {
        let cx = rect.midX
        var p = Path()
        let r: CGFloat = 6
        p.move(to: CGPoint(x: cx - top / 2 + r, y: rect.minY))
        p.addLine(to: CGPoint(x: cx + top / 2 - r, y: rect.minY))
        p.addQuadCurve(to: CGPoint(x: cx + top / 2, y: rect.minY + r), control: CGPoint(x: cx + top / 2, y: rect.minY))
        p.addCurve(to: CGPoint(x: cx + bottom / 2, y: rect.maxY),
                   control1: CGPoint(x: cx + top / 2, y: rect.midY), control2: CGPoint(x: cx + bottom / 2, y: rect.midY))
        p.addLine(to: CGPoint(x: cx - bottom / 2, y: rect.maxY))
        p.addCurve(to: CGPoint(x: cx - top / 2, y: rect.minY + r),
                   control1: CGPoint(x: cx - bottom / 2, y: rect.midY), control2: CGPoint(x: cx - top / 2, y: rect.midY))
        p.addQuadCurve(to: CGPoint(x: cx - top / 2 + r, y: rect.minY), control: CGPoint(x: cx - top / 2, y: rect.minY))
        p.closeSubpath()
        return p
    }
}

extension Snapshot {
    private static func shade(_ i: Int, of n: Int) -> Color { Theme.accent.opacity(1 - Double(i) / Double(max(n, 1)) * 0.45) }

    /// Requests: received, scanned, those that carried something sensitive, and those that
    /// brought a value never masked before (the rest re-sent earlier turns).
    var requestStages: [FunnelStage] {
        let n = funnel.withNew == nil ? 3 : 4
        var stages = [FunnelStage(label: "Requests received", value: contentRequests, color: Self.shade(0, of: n)),
                      FunnelStage(label: "Scanned before leaving", value: funnel.scanned, color: Self.shade(1, of: n)),
                      FunnelStage(label: "Carried sensitive data", value: funnel.withFindings, color: Self.shade(2, of: n))]
        if let new = funnel.withNew {
            stages.append(FunnelStage(label: "Brought new sensitive data", value: new, color: Self.shade(3, of: n)))
        }
        return stages
    }

    /// Detection: raw candidates from rules and the model, narrowed by refinement and the allowlist.
    var detectionStages: [FunnelStage] {
        let candidates = (detection["candidates_rules"] ?? 0) + (detection["candidates_model"] ?? 0)
        let refined = min(detection["after_refinement"] ?? 0, candidates)
        let allowed = min(detection["after_allowlist"] ?? 0, refined)
        let masked = min(detection["masked"] ?? 0, allowed)
        return [FunnelStage(label: "Candidates (rules + model)", value: candidates, color: Self.shade(0, of: 4)),
                FunnelStage(label: "After refinement", value: refined, color: Self.shade(1, of: 4),
                            note: candidates > 0 ? "\(percent(candidates - refined, of: candidates)) noise removed" : nil),
                FunnelStage(label: "After allowlist", value: allowed, color: Self.shade(2, of: 4)),
                FunnelStage(label: "Masked spans", value: masked, color: Theme.success, note: "overlaps merged")]
    }
}
