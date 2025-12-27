import Foundation

struct ShoppingListDTO: Codable, Identifiable, Hashable {
    let id: Int
    let name: String
    let isRecurring: Bool
    let isMain: Bool?
    let itemCount: Int?
    let createdAt: Date?
    let updatedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case isRecurring = "is_recurring"
        case isMain = "is_main"
        case itemCount = "item_count"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct ShoppingListItemDTO: Codable, Identifiable, Hashable {
    let id: Int
    let shoppingList: Int
    let recipe: Int?
    let recipeTitle: String?
    let name: String
    let amount: String?
    let unit: String?
    let checked: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case shoppingList = "shopping_list"
        case recipe
        case recipeTitle = "recipe_title"
        case name
        case amount
        case unit
        case checked
    }
}
