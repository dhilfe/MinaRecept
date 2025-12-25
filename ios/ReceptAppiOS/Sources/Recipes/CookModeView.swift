import SwiftUI

struct CookModeView: View {
    let title: String
    let steps: [String]

    @State private var index: Int = 0

    @State private var timerEndDate: Date? = nil
    @State private var now: Date = Date()

    private let tick = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Text(title)
                    .font(.headline)
                    .lineLimit(1)
                Spacer()
                Text("\(index + 1)/\(max(steps.count, 1))")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Steg \(index + 1)")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Text(currentStep)
                        .font(.title2)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    if let seconds = DurationParser.parseFirstDurationSeconds(from: currentStep) {
                        timerBlock(seconds: seconds)
                            .padding(.top, 8)
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
            }

            Divider()

            HStack(spacing: 12) {
                Button("Föregående") {
                    index = max(0, index - 1)
                    timerEndDate = nil
                }
                .buttonStyle(.bordered)
                .disabled(index == 0)

                Spacer()

                Button("Nästa") {
                    index = min(steps.count - 1, index + 1)
                    timerEndDate = nil
                }
                .buttonStyle(.borderedProminent)
                .disabled(index >= steps.count - 1)
            }
            .padding(.horizontal)
            .padding(.bottom, 12)
        }
        .navigationTitle("Cook Mode")
        .navigationBarTitleDisplayMode(.inline)
        .onReceive(tick) { _ in
            now = Date()

            if let end = timerEndDate, end.timeIntervalSince(now) <= 0 {
                timerEndDate = nil
            }
        }
    }

    private var currentStep: String {
        guard !steps.isEmpty, steps.indices.contains(index) else { return "" }
        return steps[index]
    }

    @ViewBuilder
    private func timerBlock(seconds: Int) -> some View {
        let remaining = timerRemainingSeconds

        VStack(alignment: .leading, spacing: 10) {
            Text("Timer")
                .font(.headline)

            if let remaining {
                Text(formatRemaining(remaining))
                    .font(.title3)
                    .monospacedDigit()

                HStack(spacing: 12) {
                    Button("Stoppa") { timerEndDate = nil }
                        .buttonStyle(.bordered)

                    Button("Starta om") { timerEndDate = Date().addingTimeInterval(TimeInterval(seconds)) }
                        .buttonStyle(.borderedProminent)
                }
            } else {
                Button("Starta timer: \(formatDuration(seconds))") {
                    timerEndDate = Date().addingTimeInterval(TimeInterval(seconds))
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(12)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var timerRemainingSeconds: Int? {
        guard let end = timerEndDate else { return nil }
        let remaining = Int(end.timeIntervalSince(now).rounded(.down))
        if remaining <= 0 { return 0 }
        return remaining
    }

    private func formatRemaining(_ seconds: Int) -> String {
        let minutes = seconds / 60
        let secs = seconds % 60
        if minutes >= 60 {
            let hours = minutes / 60
            let mins = minutes % 60
            return String(format: "%d:%02d:%02d", hours, mins, secs)
        }
        return String(format: "%d:%02d", minutes, secs)
    }

    private func formatDuration(_ seconds: Int) -> String {
        let minutes = seconds / 60
        if minutes >= 60 {
            let hours = minutes / 60
            let mins = minutes % 60
            if mins == 0 { return "\(hours) h" }
            return "\(hours) h \(mins) min"
        }
        return "\(minutes) min"
    }
}
