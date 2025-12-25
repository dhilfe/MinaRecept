import Foundation

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
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode) }

        do {
            let tokenResponse = try JSONDecoder().decode(TokenResponse.self, from: data)
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
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode) }

        do {
            return try JSONDecoder().decode([RecipeDTO].self, from: data)
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
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode) }

        do {
            return try JSONDecoder().decode(RecipeDTO.self, from: data)
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
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode) }

        do {
            return try JSONDecoder().decode([ShoppingListDTO].self, from: data)
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
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode) }

        do {
            return try JSONDecoder().decode([ShoppingListItemDTO].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
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
        guard (200...299).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode) }
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
