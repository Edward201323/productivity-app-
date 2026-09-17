import SwiftUI

struct CalendarView: View {
    let sessions: [Session]
    @Binding var selectedDate: Date
    let edit: (Session) -> Void
    @State private var month = Calendar.current.dateInterval(of: .month, for: .now)!.start
    private var calendar: Calendar { .current }
    private let columns = Array(repeating: GridItem(.flexible(), spacing: 4), count: 7)

    private var days: [Date?] {
        guard let range = calendar.range(of: .day, in: .month, for: month) else { return [] }
        let offset = (calendar.component(.weekday, from: month) - calendar.firstWeekday + 7) % 7
        return Array(repeating: nil, count: offset) + range.map {
            calendar.date(byAdding: .day, value: $0 - 1, to: month)
        }
    }

    private var counts: [Date: Int] {
        Dictionary(grouping: sessions, by: { calendar.startOfDay(for: $0.startDate) })
            .mapValues(\.count)
    }

    private var daySessions: [Session] {
        sessions.filter { calendar.isDate($0.startDate, inSameDayAs: selectedDate) }
            .sorted { $0.startDate > $1.startDate }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 24) {
            VStack(spacing: 14) {
                HStack {
                    Text(month.formatted(.dateTime.month(.wide).year()))
                        .font(.headline)
                    Spacer()
                    Button { moveMonth(-1) } label: { Image(systemName: "chevron.left") }
                        .help("Previous month").accessibilityLabel("Previous month")
                    Button("Today") {
                        selectedDate = .now
                        month = calendar.dateInterval(of: .month, for: selectedDate)!.start
                    }
                    Button { moveMonth(1) } label: { Image(systemName: "chevron.right") }
                        .help("Next month").accessibilityLabel("Next month")
                }
                LazyVGrid(columns: columns, spacing: 4) {
                    ForEach(0..<7, id: \.self) { index in
                        Text(calendar.veryShortStandaloneWeekdaySymbols[(index + calendar.firstWeekday - 1) % 7])
                            .font(.caption).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity).padding(.bottom, 6)
                    }
                    ForEach(days.indices, id: \.self) { index in
                        if let date = days[index] {
                            dayCell(date)
                        } else {
                            Color.clear.frame(height: 38)
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .top)

            Divider()

            VStack(alignment: .leading, spacing: 12) {
                Text(selectedDate.formatted(.dateTime.weekday(.wide).month(.abbreviated).day()))
                    .font(.headline)
                Text("\(daySessions.count) \(daySessions.count == 1 ? "session" : "sessions") · \(daySessions.count * 20) minutes")
                    .font(.caption).foregroundStyle(.secondary)
                if daySessions.isEmpty {
                    VStack(spacing: 10) {
                        Image(systemName: "square.and.pencil").font(.title).foregroundStyle(.tertiary)
                        Text("No sessions this day").foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(daySessions) { session in
                                Button { edit(session) } label: {
                                    VStack(alignment: .leading, spacing: 6) {
                                        HStack {
                                            Text(session.startDate.formatted(date: .omitted, time: .shortened))
                                            Text("–")
                                            Text((session.endDate ?? session.deadline).formatted(date: .omitted, time: .shortened))
                                            Spacer()
                                            Image(systemName: "pencil").foregroundStyle(.secondary)
                                        }
                                        .font(.caption.weight(.medium))
                                        Text(session.note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "No note" : session.note)
                                            .font(.body).foregroundStyle(.secondary)
                                            .lineLimit(3).multilineTextAlignment(.leading)
                                    }
                                    .padding(12).frame(maxWidth: .infinity, alignment: .leading)
                                    .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)
                                .help("Edit note or delete session")
                            }
                        }
                    }
                }
            }
            .frame(width: 280, alignment: .topLeading)
        }
        .frame(maxHeight: .infinity, alignment: .top)
        .onChange(of: selectedDate) { _, date in
            month = calendar.dateInterval(of: .month, for: date)!.start
        }
    }

    private func dayCell(_ date: Date) -> some View {
        let selected = calendar.isDate(date, inSameDayAs: selectedDate)
        let count = counts[calendar.startOfDay(for: date), default: 0]
        return Button { selectedDate = date } label: {
            VStack(spacing: 3) {
                Text("\(calendar.component(.day, from: date))")
                    .font(.body.weight(calendar.isDateInToday(date) ? .bold : .regular))
                Circle().fill(Color.accentColor)
                    .frame(width: 4, height: 4).opacity(count > 0 ? 1 : 0)
            }
            .frame(maxWidth: .infinity).frame(height: 38)
            .foregroundStyle(Color.primary)
            .background(selected ? Color.accentColor.opacity(0.2) : Color.clear, in: RoundedRectangle(cornerRadius: 7))
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(calendar.isDateInToday(date) && !selected ? Color.accentColor : .clear))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(date.formatted(date: .complete, time: .omitted)), \(count) sessions")
        .accessibilityAddTraits(selected ? [.isSelected] : [])
    }

    private func moveMonth(_ offset: Int) {
        if let date = calendar.date(byAdding: .month, value: offset, to: month) {
            selectedDate = date
        }
    }
}
