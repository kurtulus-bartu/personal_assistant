import SwiftUI

public struct PomodoroPage: View {
    @State private var remaining: Int = 25*60
    @State private var isRunning = false
    @State private var focusMin = 25
    @State private var breakMin = 5
    @State private var inBreak = false
    @State private var timer: Timer?
    public init() {}
    public var body: some View {
        ZStack { Theme.primaryBG.ignoresSafeArea()
            VStack(spacing: 16) {
                Text(inBreak ? "Mola" : "Odak").foregroundColor(Theme.text).font(.title2).bold()
                Text(timeString(remaining)).foregroundColor(Theme.text).font(.system(size: 48, weight: .bold, design: .rounded))
                HStack(spacing: 12) {
                    Button(isRunning ? "Duraklat" : "Başlat") { toggle() }
                        .foregroundColor(.black).padding(.vertical,10).padding(.horizontal,14)
                        .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 12))
                    Button("Sıfırla") { reset() }
                        .foregroundColor(Theme.text).padding(.vertical,10).padding(.horizontal,14)
                        .background(Theme.secondaryBG).clipShape(RoundedRectangle(cornerRadius: 12))
                }
                HStack(spacing: 12) {
                    Stepper("Odak: \(focusMin) dk", value: $focusMin, in: 10...90, step: 5).foregroundColor(Theme.text)
                    Stepper("Mola: \(breakMin) dk", value: $breakMin, in: 3...30, step: 1).foregroundColor(Theme.text)
                }.padding(.horizontal, 16)
            }.padding()
        }
        .onDisappear { timer?.invalidate() }
    }
    func toggle() { isRunning.toggle(); if isRunning { startTimer() } else { timer?.invalidate() } }
    func startTimer() { timer?.invalidate(); timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in if remaining > 0 { remaining -= 1 } else { phaseSwitch() } } }
    func phaseSwitch() { inBreak.toggle(); remaining = (inBreak ? breakMin : focusMin) * 60 }
    func reset() { inBreak = false; remaining = focusMin * 60; isRunning = false; timer?.invalidate() }
    func timeString(_ s: Int) -> String { String(format: "%02d:%02d", s/60, s%60) }
}
