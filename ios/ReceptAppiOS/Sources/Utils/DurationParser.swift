import Foundation

enum DurationParser {
    static func parseFirstDurationSeconds(from text: String) -> Int? {
        let normalized = text.lowercased()

        // 1) Combined: 1 h 30 min
        if let match = firstMatch(
            pattern: "(\\d+)\\s*(?:h|tim|timme|timmar)\\s*(\\d+)\\s*(?:min|minut|minuter)",
            in: normalized,
            groupCount: 2
        ) {
            let hours = Int(match[0]) ?? 0
            let minutes = Int(match[1]) ?? 0
            let total = hours * 3600 + minutes * 60
            return total > 0 ? total : nil
        }

        // 2) Hours only
        if let match = firstMatch(
            pattern: "(\\d+)\\s*(?:h|tim|timme|timmar)",
            in: normalized,
            groupCount: 1
        ) {
            let hours = Int(match[0]) ?? 0
            let total = hours * 3600
            return total > 0 ? total : nil
        }

        // 3) Minutes only
        if let match = firstMatch(
            pattern: "(\\d+)\\s*(?:min|minut|minuter)",
            in: normalized,
            groupCount: 1
        ) {
            let minutes = Int(match[0]) ?? 0
            let total = minutes * 60
            return total > 0 ? total : nil
        }

        return nil
    }

    private static func firstMatch(pattern: String, in text: String, groupCount: Int) -> [String]? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else { return nil }
        let range = NSRange(text.startIndex..<text.endIndex, in: text)
        guard let match = regex.firstMatch(in: text, options: [], range: range) else { return nil }

        var groups: [String] = []
        for idx in 1...(groupCount) {
            let r = match.range(at: idx)
            guard let swiftRange = Range(r, in: text) else { return nil }
            groups.append(String(text[swiftRange]))
        }
        return groups
    }
}
