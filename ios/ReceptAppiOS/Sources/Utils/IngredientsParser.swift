import Foundation

enum IngredientsParser {
    static func parse(_ raw: String?) -> [IngredientDTO] {
        guard let raw, !raw.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return []
        }

        // Backend skickar ingredients som en JSON-sträng.
        if let data = raw.data(using: .utf8) {
            if let decoded = try? JSONDecoder().decode([IngredientDTO].self, from: data) {
                return decoded
            }
        }

        // Fallback: tolka som rad-separerad text
        let lines = raw
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        return lines.map { IngredientDTO(amount: nil, unit: nil, name: $0) }
    }
}
