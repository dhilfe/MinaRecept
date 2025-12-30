import XCTest

class InfoPlistAPITests: XCTestCase {
    func testAPIBaseURLIsProductionInRelease() {
        #if !DEBUG
        let url = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String
        XCTAssertEqual(url, "https://api.receptapp.se/api/", "Release build ska använda produktions-URL")
        #endif
    }
}
