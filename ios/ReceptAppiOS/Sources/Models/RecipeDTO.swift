import Foundation

struct RecipeDTO: Codable, Identifiable, Hashable {
    let id: Int
    let title: String
    let description: String?
    let ingredients: String?
    let steps: String?
    let cookingTime: Int?
    let imageURL: URL?
    let dishType: String?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case description
        case ingredients
        case steps
        case cookingTime = "cooking_time"
        case imageURL = "image_url"
        case dishType = "dish_type"
    }
    
    var dishTypeDisplayName: String {
        switch dishType {
        case "breakfast": return "Frukost"
        case "lunch", "dinner", "lunch_dinner": return "Lunch/Middag"
        case "appetizer": return "Förrätt"
        case "dessert": return "Efterrätt"
        case "snack": return "Mellanmål"
        case "everyday": return "Lunch/Middag"
        case "party": return "Fest"
        case "vegetarian": return "Vegetariskt"
        case "other": return "Övrigt"
        default: return dishType ?? ""
        }
    }

    var preferredImageURL: URL? {
        guard let imageURL else { return nil }
        guard imageURL.scheme?.lowercased() == "http" else { return imageURL }

        var components = URLComponents(url: imageURL, resolvingAgainstBaseURL: false)
        components?.scheme = "https"
        return components?.url ?? imageURL
    }

    static let allDishTypes: [(id: String, name: String)] = [
        ("breakfast", "Frukost"),
        ("lunch_dinner", "Lunch/Middag"),
        ("appetizer", "Förrätt"),
        ("dessert", "Efterrätt"),
        ("snack", "Mellanmål"),
        ("party", "Fest"),
        ("vegetarian", "Vegetariskt"),
        ("other", "Övrigt")
    ]
}

struct IngredientDTO: Codable, Identifiable {
    var id: String { "\(name ?? "")|\(amount ?? "")|\(unit ?? "")" }

    let amount: String?
    let unit: String?
    let name: String?
}
