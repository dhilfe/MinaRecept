import Foundation

struct RecipeDTO: Codable, Identifiable, Hashable {
    let id: Int
    let title: String
    let description: String?
    let ingredients: String?
    let steps: String?
    let imageURL: URL?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case description
        case ingredients
        case steps
        case imageURL = "image_url"
    }
}

struct IngredientDTO: Codable, Identifiable {
    var id: String { "\(name ?? "")|\(amount ?? "")|\(unit ?? "")" }

    let amount: String?
    let unit: String?
    let name: String?
}
