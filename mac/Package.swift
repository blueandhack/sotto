// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Keepmum",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "Keepmum", path: "Sources/Keepmum"),
    ]
)
