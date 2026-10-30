import Charts
import SwiftUI

/// Masked values by type as labeled horizontal bars, in one color.
struct TypeBars: View {
    var counts: [String: Int]

    var body: some View {
        let rows = Theme.typeOrder.compactMap { t in counts[t].flatMap { $0 > 0 ? (t, $0) : nil } }
        let top = Double(rows.map(\.1).max() ?? 1)
        VStack(alignment: .leading, spacing: 9) {
            if rows.isEmpty {
                Text("Nothing masked yet").font(.system(size: 12)).foregroundStyle(Theme.secondary)
            }
            ForEach(rows, id: \.0) { type, n in
                HStack(spacing: 10) {
                    Image(systemName: Theme.icon(type)).font(.system(size: 11)).foregroundStyle(Theme.secondary).frame(width: 16)
                    Text(Theme.label(type)).font(.system(size: 12)).foregroundStyle(Theme.text).frame(width: 74, alignment: .leading)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Theme.faint)
                            Capsule().fill(Theme.accent.opacity(type == "SECRET" ? 1 : 0.55))
                                .frame(width: max(4, geo.size.width * Double(n) / top))
                        }
                    }
                    .frame(height: 8)
                    Text(n.compact).font(.system(size: 12, weight: .semibold)).monospacedDigit().foregroundStyle(Theme.text)
                        .frame(width: 40, alignment: .trailing)
                }
            }
        }
    }
}

struct MaskedTimeline: View {
    var minutes: [Snapshot.Minute]

    var body: some View {
        // Only the minutes inside the axis: Swift Charts does not clip marks outside its domain.
        let start = Date().addingTimeInterval(-3600)
        let recent = minutes.filter { $0.date >= start }
        Chart {
            ForEach(recent) { m in
                BarMark(x: .value("Minute", m.date, unit: .minute), y: .value("Masked", m.masked.values.reduce(0, +)))
                    .foregroundStyle(Theme.accent.opacity(0.75))
                    .cornerRadius(4)
                if m.blocked > 0 {
                    PointMark(x: .value("Minute", m.date, unit: .minute), y: .value("Blocked", 0))
                        .symbol(.circle).symbolSize(36).foregroundStyle(Theme.danger)
                }
            }
        }
        .chartXScale(domain: start...Date().addingTimeInterval(420))
        .chartPlotStyle { $0.clipped() }
        .chartXAxis { AxisMarks(values: .stride(by: .minute, count: 20)) { _ in
            AxisGridLine().foregroundStyle(Theme.border)
            AxisValueLabel(format: .dateTime.hour().minute()).foregroundStyle(Theme.secondary)
        } }
        .chartYAxis { AxisMarks(position: .leading) { _ in
            AxisGridLine().foregroundStyle(Theme.border)
            AxisValueLabel().foregroundStyle(Theme.secondary)
        } }
    }
}

struct LatencyChart: View {
    var events: [Snapshot.Event]
    static let budget = 150.0

    var body: some View {
        let points = Array(events.compactMap { e in e.scanMs.map { (e.date, $0) } }.suffix(120))
        Chart {
            ForEach(Array(points.enumerated()), id: \.offset) { _, pt in
                AreaMark(x: .value("Time", pt.0), y: .value("ms", pt.1))
                    .foregroundStyle(Theme.accentSoft).interpolationMethod(.monotone)
                LineMark(x: .value("Time", pt.0), y: .value("ms", pt.1))
                    .foregroundStyle(Theme.accent).interpolationMethod(.monotone)
                    .lineStyle(StrokeStyle(lineWidth: 1.6))
            }
            RuleMark(y: .value("Budget", Self.budget))
                .foregroundStyle(Theme.danger.opacity(0.6))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
                .annotation(position: .top, alignment: .trailing) {
                    Text("budget \(Int(Self.budget)) ms").font(.system(size: 10)).foregroundStyle(Theme.secondary)
                }
        }
        .chartYScale(domain: 0...max(Self.budget * 1.3, points.map(\.1).max() ?? 0))
        .chartPlotStyle { $0.clipped() }
        .chartXAxis { AxisMarks { _ in
            AxisGridLine().foregroundStyle(Theme.border)
            AxisValueLabel(format: .dateTime.hour().minute()).foregroundStyle(Theme.secondary)
        } }
        .chartYAxis { AxisMarks(position: .leading) { _ in
            AxisGridLine().foregroundStyle(Theme.border)
            AxisValueLabel().foregroundStyle(Theme.secondary)
        } }
    }
}

/// How scan times are distributed, in 25 ms buckets; buckets over the budget are red.
struct LatencyHistogram: View {
    var events: [Snapshot.Event]

    var body: some View {
        let times = events.compactMap(\.scanMs)
        let buckets: [(label: String, count: Int, over: Bool)] = stride(from: 0, to: 250, by: 25).map { lo in
            let last = lo >= 225
            let n = times.filter { $0 >= Double(lo) && (last || $0 < Double(lo + 25)) }.count
            return (last ? "225+" : "\(lo)", n, lo >= 150)
        }
        Chart(buckets, id: \.label) { b in
            BarMark(x: .value("ms", b.label), y: .value("Requests", b.count))
                .foregroundStyle(b.over ? Theme.danger.opacity(0.7) : Theme.accent.opacity(0.75))
                .cornerRadius(5)
        }
        .chartXAxis { AxisMarks { _ in AxisValueLabel().foregroundStyle(Theme.secondary) } }
        .chartYAxis { AxisMarks(position: .leading) { _ in
            AxisGridLine().foregroundStyle(Theme.border)
            AxisValueLabel().foregroundStyle(Theme.secondary)
        } }
    }
}
