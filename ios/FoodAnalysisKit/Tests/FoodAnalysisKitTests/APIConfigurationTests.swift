import XCTest

@testable import FoodAnalysisKit

final class APIConfigurationTests: XCTestCase {
    func testMissingOverrideOnSimulatorDefaultsToLocalhost() {
        let result = APIConfiguration.resolve(rawOverride: nil, allowsImplicitSimulatorDefault: true)

        XCTAssertEqual(try? result.get(), URL(string: "http://127.0.0.1:7071/api"))
    }

    func testBlankOverrideOnSimulatorDefaultsToLocalhost() {
        let result = APIConfiguration.resolve(rawOverride: "   ", allowsImplicitSimulatorDefault: true)

        XCTAssertEqual(try? result.get(), URL(string: "http://127.0.0.1:7071/api"))
    }

    func testMissingOverrideOffSimulatorFailsClosed() {
        let result = APIConfiguration.resolve(rawOverride: nil, allowsImplicitSimulatorDefault: false)

        guard case .failure(.missingConfiguration) = result else {
            return XCTFail("Expected .missingConfiguration, got \(result)")
        }
    }

    func testMalformedOverrideNeverFallsBackToLocalhostEvenOnSimulator() {
        // The core fix for finding #4: an explicitly-set but invalid value
        // must never be silently replaced by the local default.
        let result = APIConfiguration.resolve(rawOverride: "not a url", allowsImplicitSimulatorDefault: true)

        guard case .failure(.invalidURL) = result else {
            return XCTFail("Expected .invalidURL, got \(result)")
        }
    }

    func testUnsupportedSchemeFails() {
        let result = APIConfiguration.resolve(rawOverride: "ftp://host/api", allowsImplicitSimulatorDefault: true)

        guard case .failure(.unsupportedScheme("ftp")) = result else {
            return XCTFail("Expected .unsupportedScheme(\"ftp\"), got \(result)")
        }
    }

    func testHTTPToNonLocalHostFails() {
        let result = APIConfiguration.resolve(
            rawOverride: "http://api.example.com/api",
            allowsImplicitSimulatorDefault: true
        )

        guard case .failure(.insecureSchemeForNonLocalHost(host: "api.example.com")) = result else {
            return XCTFail("Expected .insecureSchemeForNonLocalHost, got \(result)")
        }
    }

    func testHTTPSToNonLocalHostSucceeds() {
        let result = APIConfiguration.resolve(
            rawOverride: "https://api.example.com/api",
            allowsImplicitSimulatorDefault: true
        )

        XCTAssertEqual(try? result.get(), URL(string: "https://api.example.com/api"))
    }

    func testHTTPToLoopbackSucceeds() {
        let result = APIConfiguration.resolve(
            rawOverride: "http://127.0.0.1:7071/api",
            allowsImplicitSimulatorDefault: false
        )

        XCTAssertEqual(try? result.get(), URL(string: "http://127.0.0.1:7071/api"))
    }

    func testHTTPToPrivateLANHostSucceedsForPhysicalDeviceUseCase() {
        let result = APIConfiguration.resolve(
            rawOverride: "http://192.168.1.23:7071",
            allowsImplicitSimulatorDefault: false
        )

        XCTAssertEqual(try? result.get(), URL(string: "http://192.168.1.23:7071/api"))
    }

    func testHTTPToNonPrivateIPFails() {
        // A public IP literal is not treated as a recognized local address.
        let result = APIConfiguration.resolve(rawOverride: "http://8.8.8.8/api", allowsImplicitSimulatorDefault: true)

        guard case .failure(.insecureSchemeForNonLocalHost(host: "8.8.8.8")) = result else {
            return XCTFail("Expected .insecureSchemeForNonLocalHost, got \(result)")
        }
    }

    func testPathNormalizationAppendsAPIWhenMissing() {
        let result = APIConfiguration.resolve(
            rawOverride: "https://api.example.com",
            allowsImplicitSimulatorDefault: true
        )

        XCTAssertEqual(try? result.get(), URL(string: "https://api.example.com/api"))
    }

    func testPathNormalizationLeavesExistingAPISuffixUnchanged() {
        let result = APIConfiguration.resolve(
            rawOverride: "https://api.example.com/api",
            allowsImplicitSimulatorDefault: true
        )

        XCTAssertEqual(try? result.get(), URL(string: "https://api.example.com/api"))
    }
}
