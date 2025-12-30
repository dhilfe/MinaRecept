import XCTest
@testable import ReceptAppiOS

class SessionControllerAppGroupTests: XCTestCase {
    let suiteName = "group.se.receptapp.ios"
    let tokenKey = "auth_token"
    let testToken = "test_token_123"

    override func setUp() {
        super.setUp()
        // Clean up before each test
        UserDefaults(suiteName: suiteName)?.removeObject(forKey: tokenKey)
    }

    override func tearDown() {
        // Clean up after each test
        UserDefaults(suiteName: suiteName)?.removeObject(forKey: tokenKey)
        super.tearDown()
    }

    @MainActor
    func testTokenIsSharedToAppGroupUserDefaults() async {
        let session = SessionController(tokenStore: MockTokenStore())
        session.setToken(testToken)
        let sharedToken = UserDefaults(suiteName: suiteName)?.string(forKey: tokenKey)
        XCTAssertEqual(sharedToken, testToken, "Token should be written to App Group UserDefaults")
    }

    @MainActor
    func testTokenIsRemovedFromAppGroupUserDefaultsOnLogout() async {
        let session = SessionController(tokenStore: MockTokenStore())
        session.setToken(testToken)
        session.logout()
        let sharedToken = UserDefaults(suiteName: suiteName)?.string(forKey: tokenKey)
        XCTAssertNil(sharedToken, "Token should be removed from App Group UserDefaults on logout")
    }
}

class MockTokenStore: TokenStoring {
    private var token: String?
    func loadToken() -> String? { token }
    func saveToken(_ token: String) { self.token = token }
    func clearToken() { self.token = nil }
}
