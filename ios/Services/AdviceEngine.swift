import Foundation

public final class AdviceEngine {
    public init() {}
    public func makeAdvice(activity: ActivitySnapshot, weights: [WeightEntry]) -> [Advice] {
        var tips: [Advice] = []
        if activity.steps < 6000 {
            tips.append(Advice(title: "Günlük adımı artır", details: "\(max(15, (6000-activity.steps)/300)) dk tempolu yürüyüş ekle.", category: .exercise))
        }
        if activity.activeEnergyKcal < 400 {
            tips.append(Advice(title: "Aktif enerji hedefi", details: "Bugün \(Int(400-activity.activeEnergyKcal)) kcal daha hareket hedefi.", category: .exercise))
        }
        tips.append(Advice(title: "Günlük menü önerisi", details: "Kahvaltı: Yulaf + yoğurt + meyve. Öğle: Izgara tavuk + salata + bulgur. Akşam: Zeytinyağlı sebze + yoğurt.", category: .nutrition))
        return tips
    }
}
