import XCTest
@testable import ReceptAppShare

class ShareViewControllerAppGroupTests: XCTestCase {
    let suiteName = "group.se.receptapp.ios"
    let tokenKey = "auth_token"
    let testToken = "test_token_456"

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

    func testShareExtensionReadsTokenFromAppGroupUserDefaults() {
        UserDefaults(suiteName: suiteName)?.set(testToken, forKey: tokenKey)
        let token = UserDefaults(suiteName: suiteName)?.string(forKey: tokenKey)
        XCTAssertEqual(token, testToken, "Share Extension should read token from App Group UserDefaults")
    }
}
