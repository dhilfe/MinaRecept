import SwiftUI

struct WelcomePagesView: View {
    @State private var page = 0
    let pageCount = 4
    var body: some View {
        TabView(selection: $page) {
            WelcomePage1().tag(0)
            WelcomePage2().tag(1)
            WelcomePage3().tag(2)
            WelcomePage4().tag(3)
        }
        .tabViewStyle(PageTabViewStyle(indexDisplayMode: .always))
        .animation(.easeInOut, value: page)
    }
}

struct WelcomePage1: View {
    var body: some View {
        VStack(spacing: 32) {
            Image(systemName: "book.fill")
                .resizable()
                .scaledToFit()
                .frame(height: 120)
                .foregroundColor(.accentColor)
            Text("Välkommen till MinaRecept")
                .font(.largeTitle)
                .fontWeight(.bold)
            Text("Samla och upptäck recept på ett ställe. Din digitala kokbok!")
                .font(.title3)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}

struct WelcomePage2: View {
    var body: some View {
        VStack(spacing: 32) {
            Image(systemName: "list.bullet.rectangle")
                .resizable()
                .scaledToFit()
                .frame(height: 120)
                .foregroundColor(.accentColor)
            Text("Planera din vecka")
                .font(.title)
                .fontWeight(.bold)
            Text("Skapa veckomenyer och få smarta inköpslistor automatiskt.")
                .font(.title3)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}

struct WelcomePage3: View {
    var body: some View {
        VStack(spacing: 32) {
            Image(systemName: "cart.fill")
                .resizable()
                .scaledToFit()
                .frame(height: 120)
                .foregroundColor(.accentColor)
            Text("Handla enkelt")
                .font(.title)
                .fontWeight(.bold)
            Text("Få en komplett inköpslista direkt i mobilen – redo för butiken.")
                .font(.title3)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}

struct WelcomePage4: View {
    var body: some View {
        VStack(spacing: 32) {
            Image(systemName: "sparkles")
                .resizable()
                .scaledToFit()
                .frame(height: 120)
                .foregroundColor(.accentColor)
            Text("Börja inspireras!")
                .font(.title)
                .fontWeight(.bold)
            Text("Utforska nya recept och gör matlagningen roligare varje dag.")
                .font(.title3)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}

struct WelcomePagesView_Previews: PreviewProvider {
    static var previews: some View {
        WelcomePagesView()
    }
}
