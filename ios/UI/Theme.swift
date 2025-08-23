import SwiftUI

public struct Theme {
    public static let primaryBG = Color(hex: "#212121")
    public static let secondaryBG = Color(hex: "#2d2d2d")
    public static let accent      = Color(hex: "#11989C")
    public static let text        = Color(hex: "#EEEEEE")
    public static let textMuted   = Color(hex: "#AEAEAE")
}

public extension Color {
    init(hex: String) {
        var s = hex
        if s.hasPrefix("#") { s.removeFirst() }
        var v: UInt64 = 0
        Scanner(string: s).scanHexInt64(&v)
        let r = Double((v >> 16) & 0xFF) / 255
        let g = Double((v >> 8) & 0xFF) / 255
        let b = Double(v & 0xFF) / 255
        self = Color(.sRGB, red: r, green: g, blue: b, opacity: 1)
    }
}
