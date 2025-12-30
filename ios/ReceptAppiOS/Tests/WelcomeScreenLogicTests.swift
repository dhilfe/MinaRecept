import XCTest
@testable import ReceptAppiOS

class WelcomeScreenLogicTests: XCTestCase {
    let firstLaunchKey = "hasSeenWelcomeScreen"

    override func setUp() {
        super.setUp()
        UserDefaults.standard.removeObject(forKey: firstLaunchKey)
    }

    override func tearDown() {
        UserDefaults.standard.removeObject(forKey: firstLaunchKey)
        super.tearDown()
    }

    func testWelcomeScreenIsShownOnFirstLaunch() {
        let hasSeen = UserDefaults.standard.bool(forKey: firstLaunchKey)
        XCTAssertFalse(hasSeen, "Welcome screen should be shown on first launch")
    }

    func testWelcomeScreenIsNotShownAfterContinue() {
        UserDefaults.standard.set(true, forKey: firstLaunchKey)
        let hasSeen = UserDefaults.standard.bool(forKey: firstLaunchKey)
        XCTAssertTrue(hasSeen, "Welcome screen should not be shown after continue")
    }
}
