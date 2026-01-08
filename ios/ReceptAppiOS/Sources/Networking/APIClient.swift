import Foundation
import os

private let apiLogger = Logger(subsystem: "se.receptapp.ios", category: "APIClient")

final class APIClient {
    static let shared = APIClient()

    private static let defaultSession: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
        config.waitsForConnectivity = false
        return URLSession(configuration: config)
    }()

    private let session: URLSession
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: dateString) {
                return date
            }
            
            formatter.formatOptions = [.withInternetDateTime]
            if let date = formatter.date(from: dateString) {
                return date
            }
            
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid date format: \(dateString)")
        }
        return decoder
    }()

    init(session: URLSession = APIClient.defaultSession) {
        self.session = session
    }

    private func url(_ relativePath: String) throws -> URL {
        guard let url = URL(string: relativePath, relativeTo: AppConfig.apiBaseURL) else {
            throw APIError.invalidURL
        }
        return url
    }

    private func url(_ relativePath: String, queryItems: [URLQueryItem]) throws -> URL {
        let base = try url(relativePath)
        guard var components = URLComponents(url: base, resolvingAgainstBaseURL: true) else {
            throw APIError.invalidURL
        }
        components.queryItems = queryItems
        guard let withQuery = components.url else {
            throw APIError.invalidURL
        }
        return withQuery
    }

    func login(username: String, password: String) async throws -> String {
        let url = try url("auth/token/")
        apiLogger.info("POST \(url.absoluteString, privacy: .public) (login username/password)")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = LoginRequest(username: username, password: password)
        request.httpBody = try JSONEncoder().encode(body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            let tokenResponse = try decoder.decode(TokenResponse.self, from: data)
            return tokenResponse.token
        } catch {
            throw APIError.decoding(error)
        }
    }

    func loginWithApple(idToken: String, firstName: String?, lastName: String?) async throws -> String {
        let url = try url("auth/apple/")
        apiLogger.info("POST \(url.absoluteString, privacy: .public) (login apple)")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["id_token": idToken]
        if let firstName { body["first_name"] = firstName }
        if let lastName { body["last_name"] = lastName }
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { 
            // Try to extract error details
            var message: String?
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = json["detail"] as? String {
                message = detail
            }
            throw APIError.httpStatus(http.statusCode, message) 
        }

        do {
            let tokenResponse = try decoder.decode(TokenResponse.self, from: data)
            return tokenResponse.token
        } catch {
            throw APIError.decoding(error)
        }
    }

    func fetchRecipes(token: String) async throws -> [RecipeDTO] {
        let url = try url("recipes/")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode([RecipeDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func fetchRecipe(id: Int, token: String) async throws -> RecipeDTO {
        let url = try url("recipes/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode(RecipeDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func updateRecipe(id: Int, fields: [String: Any], token: String) async throws -> RecipeDTO {
        let url = try url("recipes/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        request.httpBody = try JSONSerialization.data(withJSONObject: fields)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode(RecipeDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func createRecipe(
        title: String,
        description: String,
        ingredients: String,
        steps: String,
        cookingTime: Int,
        servings: Int,
        dishType: String,
        tags: String,
        token: String
    ) async throws -> RecipeDTO {
        let url = try url("recipes/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "title": title,
            "description": description,
            "ingredients": ingredients,
            "steps": steps,
            "cooking_time": cookingTime,
            "servings": servings,
            "dish_type": dishType,
        ]
        if !tags.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            body["tags"] = tags
        }

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode(RecipeDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func createShoppingList(name: String, isRecurring: Bool, token: String) async throws -> ShoppingListDTO {
        let url = try url("shopping-lists/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["name": name, "is_recurring": isRecurring] as [String : Any]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode(ShoppingListDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func fetchShoppingLists(token: String) async throws -> [ShoppingListDTO] {
        let url = try url("shopping-lists/")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode([ShoppingListDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func deleteShoppingList(id: Int, token: String) async throws {
        let url = try url("shopping-lists/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func clearShoppingList(id: Int, token: String) async throws {
        let url = try url("shopping-lists/\(id)/clear/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func uncheckAllShoppingListItems(id: Int, token: String) async throws {
        let url = try url("shopping-lists/\(id)/uncheck-all/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func addShoppingListItem(shoppingListId: Int, name: String, amount: String? = nil, unit: String? = nil, token: String) async throws -> ShoppingListItemDTO {
        let url = try url("shopping-list-items/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "shopping_list": shoppingListId,
            "name": name,
            "amount": amount ?? "",
            "unit": unit ?? "",
            "checked": false
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode(ShoppingListItemDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func fetchShoppingListItems(shoppingListId: Int, token: String) async throws -> [ShoppingListItemDTO] {
        let url = try url(
            "shopping-list-items/",
            queryItems: [URLQueryItem(name: "shopping_list", value: String(shoppingListId))]
        )
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode([ShoppingListItemDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func updateShoppingListItem(id: Int, checked: Bool, token: String) async throws -> ShoppingListItemDTO {
        let url = try url("shopping-list-items/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["checked": checked]
        request.httpBody = try JSONEncoder().encode(body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode(ShoppingListItemDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func deleteShoppingListItem(id: Int, token: String) async throws {
        let url = try url("shopping-list-items/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func addIngredientsToShoppingList(recipeId: Int, shoppingListId: Int?, token: String) async throws {
        let url = try url("recipes/\(recipeId)/add-to-shopping-list/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = AddToShoppingListRequest(shopping_list_id: shoppingListId)
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func fetchWeeklyPlan(token: String) async throws -> [WeeklyPlanDTO] {
        let url = try url("weekly-plan/")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode([WeeklyPlanDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func randomizeWeeklyPlan(token: String) async throws -> [WeeklyPlanDTO] {
        let url = try url("weekly-plan/randomize/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        
        if !(200...299).contains(http.statusCode) {
            var message: String?
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = json["detail"] as? String {
                message = detail
            }
            throw APIError.httpStatus(http.statusCode, message)
        }

        do {
            return try decoder.decode([WeeklyPlanDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func addToWeeklyPlan(day: String, recipeId: Int, token: String) async throws -> WeeklyPlanDTO {
        let url = try url("weekly-plan/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["day": day, "recipe": recipeId] as [String : Any]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode(WeeklyPlanDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func deleteRecipe(id: Int, token: String) async throws {
        let url = try url("recipes/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func deleteFromWeeklyPlan(id: Int, token: String) async throws {
        let url = try url("weekly-plan/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func saveWeeklyPlanAsMenu(name: String?, servings: Int?, token: String) async throws {
        let url = try url("weekly-plan/save-as-menu/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [:]
        if let name = name, !name.isEmpty {
            body["name"] = name
        }
        if let servings = servings {
            body["servings"] = servings
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func fetchWeeklyMenus(token: String) async throws -> [WeeklyMenuDTO] {
        let url = try url("weekly-menus/")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode([WeeklyMenuDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func deleteWeeklyMenu(id: Int, token: String) async throws {
        let url = try url("weekly-menus/\(id)/")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }
    }

    func fetchWeeklyMenuShoppingList(menuId: Int, token: String) async throws -> [WeeklyMenuShoppingListCategoryDTO] {
        let url = try url("weekly-menus/\(menuId)/shopping-list/")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode, nil) }

        do {
            return try decoder.decode([WeeklyMenuShoppingListCategoryDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func importRecipe(url sharedURL: String, token: String) async throws {
        let endpoint = try url("recipes/import/")
        apiLogger.info("POST \(endpoint.absoluteString, privacy: .public) body.url=\(sharedURL, privacy: .public)")

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = ["url": sharedURL]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }

        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }

        apiLogger.info("importRecipe status=\(http.statusCode)")

        guard (200...299).contains(http.statusCode) else {
            var message: String?
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                if let detail = json["detail"] as? String { message = detail }
                if message == nil, let error = json["error"] as? String { message = error }
            }
            throw APIError.httpStatus(http.statusCode, message)
        }
    }
}

private struct LoginRequest: Codable {
    let username: String
    let password: String
}

private struct TokenResponse: Codable {
    let token: String
}

private struct AddToShoppingListRequest: Codable {
    let shopping_list_id: Int?
}
