import SwiftUI

struct WelcomeView: View {
    var onContinue: () -> Void
    var body: some View {
        VStack(spacing: 32) {
            Text("Välkommen till MinaRecept")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            Text("Din nya plats för recept och inspiration!")
                .font(.title3)
                .multilineTextAlignment(.center)
            Button(action: onContinue) {
                Text("Kom igång")
                    .font(.headline)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color.accentColor)
                    .foregroundColor(.white)
                    .cornerRadius(12)
            }
        }
        .padding()
    }
}

struct WelcomeView_Previews: PreviewProvider {
    static var previews: some View {
        WelcomeView(onContinue: {})
    }
}
