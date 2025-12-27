import Foundation

struct WeeklyPlanDTO: Codable, Identifiable {
    let id: Int
    let day: String
    let recipe: Int
    let recipeTitle: String

    enum CodingKeys: String, CodingKey {
        case id
        case day
        case recipe
        case recipeTitle = "recipe_title"
    }
}

struct WeeklyMenuDTO: Identifiable, Codable {
    let id: Int
    let name: String
    let weekNumber: Int?
    let year: Int?
    let createdAt: Date
    let items: [WeeklyMenuItemDTO]
    
    enum CodingKeys: String, CodingKey {
        case id
        case name
        case weekNumber = "week_number"
        case year
        case createdAt = "created_at"
        case items
    }
}

struct WeeklyMenuItemDTO: Identifiable, Codable {
    let id: Int
    let menu: Int
    let day: String
    let recipe: Int
    let recipeTitle: String
    
    enum CodingKeys: String, CodingKey {
        case id
        case menu
        case day
        case recipe
        case recipeTitle = "recipe_title"
    }
}

struct WeeklyMenuShoppingListItemDTO: Codable, Identifiable {
    var id: String { name + unit }
    let name: String
    let amount: String
    let unit: String
    let category: String
}

struct WeeklyMenuShoppingListCategoryDTO: Codable, Identifiable {
    var id: String { category }
    let category: String
    let items: [WeeklyMenuShoppingListItemDTO]
}

