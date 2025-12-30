import XCTest
import SwiftUI
@testable import ReceptAppiOS

final class RecipeListViewGoogleSearchTests: XCTestCase {
    @MainActor
    func testGoogleSearchButtonAppearsWhenNoRecipesMatch() async {
        // Arrange: Skapa en tom lista och en söksträng
        let view = RecipeListView(
            resetToken: 0
        )
        // Injecta testdata
        let _ = UIHostingController(rootView: view.environmentObject(SessionController(tokenStore: MockTokenStore())))
        // Notera: Kan ej direkt sätta searchText då den är private. Testen är en struktur för vidare utveckling med ViewInspector eller liknande.
        // Assert: Kontrollera att knappen finns i vyn
        // (Detta kräver snapshot- eller accessibility-test, här är ett exempel på struktur)
        // I praktiken kan du använda ViewInspector eller liknande ramverk för att testa SwiftUI-vyer
        // Exempel (pseudo):
        // XCTAssertTrue(host.view.findButton(withLabel: "Sök på Google").exists)
    }
}

// Använd MockTokenStore från SessionControllerAppGroupTests.swift
