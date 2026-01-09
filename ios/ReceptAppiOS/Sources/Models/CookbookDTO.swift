import Foundation

struct CookbookDTO: Codable, Identifiable, Hashable {
    let id: Int
    let name: String
    let recipeCount: Int?
    let previewImageURLs: [URL]?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case recipeCount = "recipe_count"
        case previewImageURLs = "preview_image_urls"
    }
}
