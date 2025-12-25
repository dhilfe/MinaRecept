import Foundation

struct ShoppingListDTO: Codable, Identifiable, Hashable {
    let id: Int
    let name: String
    let isRecurring: Bool
    let isMain: Bool?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case isRecurring = "is_recurring"
        case isMain = "is_main"
    }
}

struct ShoppingListItemDTO: Codable, Identifiable, Hashable {
    let id: Int
    let shoppingList: Int
    let recipe: Int?
    let name: String
    let amount: String?
    let unit: String?
    let checked: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case shoppingList = "shopping_list"
        case recipe
        case name
        case amount
        case unit
        case checked
    }
}
