import SwiftUI

public struct StatCard: View {
    public var title: String
    public var value: String
    public var subtitle: String
    public init(title: String, value: String, subtitle: String) {
        self.title = title; self.value = value; self.subtitle = subtitle
    }
    public var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).foregroundColor(Theme.textMuted).font(.subheadline)
            Text(value).foregroundColor(Theme.text).font(.title3).bold()
            Text(subtitle).foregroundColor(Theme.textMuted).font(.caption)
        }
        .padding(14)
        .background(Theme.secondaryBG)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.accent.opacity(0.6), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

public struct SectionTitle: View {
    public var text: String
    public init(_ t: String) { self.text = t }
    public var body: some View { Text(text).foregroundColor(Theme.text).font(.headline) }
}

public struct AdviceRow: View {
    public let tip: Advice
    public init(tip: Advice) { self.tip = tip }
    var icon: String { switch tip.category { case .nutrition: return "fork.knife"; case .exercise: return "figure.walk"; case .lifestyle: return "heart.text.square" } }
    public var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon).foregroundColor(Theme.accent).frame(width: 24)
            VStack(alignment: .leading, spacing: 4) {
                Text(tip.title).foregroundColor(Theme.text).bold()
                Text(tip.details).foregroundColor(Theme.textMuted)
            }
            Spacer()
        }
        .padding(12)
        .background(Theme.secondaryBG)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
