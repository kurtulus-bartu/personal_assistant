import SwiftUI
import EventKit
import EventKitUI
import UIKit

public struct CalendarPage: View {
    @State private var granted = false
    @State private var events: [EKEvent] = []
    private let store = EKEventStore()
    public init() {}
    public var body: some View {
        ZStack { Theme.primaryBG.ignoresSafeArea()
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Takvim").foregroundColor(Theme.text).font(.title2).bold()
                    Spacer()
                    Button("Etkinlik Ekle") { presentEditor() }
                        .foregroundColor(.black)
                        .padding(.vertical, 8).padding(.horizontal, 12)
                        .background(Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                }.padding(.horizontal,16).padding(.top,12)

                List(events, id: \.eventIdentifier) { ev in
                    VStack(alignment: .leading) {
                        Text(ev.title ?? "(Başlık yok)").font(.headline)
                        Text("\(ev.startDate.formatted()) – \(ev.endDate?.formatted() ?? "?")")
                            .font(.caption).foregroundColor(.secondary)
                    }
                }.listStyle(.plain)
            }
        }
        .onAppear { requestAccessAndLoad() }
    }

    func requestAccessAndLoad() {
        store.requestAccess(to: .event) { ok, _ in
            DispatchQueue.main.async { self.granted = ok; if ok { self.loadUpcoming() } }
        }
    }

    func loadUpcoming() {
        let start = Date()
        let end = Calendar.current.date(byAdding: .day, value: 14, to: start)!
        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
        self.events = store.events(matching: predicate).sorted { $0.startDate < $1.startDate }
    }

    func presentEditor() {
        guard let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let root = scene.windows.first?.rootViewController else { return }
        let vc = EKEventEditViewController()
        vc.eventStore = store
        vc.editViewDelegate = EKEditDelegateWrapper { _ in self.loadUpcoming(); root.dismiss(animated: true) }
        root.present(vc, animated: true)
    }
}

final class EKEditDelegateWrapper: NSObject, EKEventEditViewDelegate {
    let onEnd: (EKEventEditViewAction) -> Void
    init(onEnd: @escaping (EKEventEditViewAction) -> Void) { self.onEnd = onEnd }
    func eventEditViewController(_ controller: EKEventEditViewController, didCompleteWith action: EKEventEditViewAction) { onEnd(action) }
}
