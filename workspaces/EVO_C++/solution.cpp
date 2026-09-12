int countSetBits(int n) {
    if (n < 0) {
        throw std::invalid_argument("Input must be a non-negative integer.");
    }
    
    int count = 0;
    while (n > 0) {
        count += n & 1;
        n >>= 1;
    }
    return count;
}

// === INJECTED TEST HARNESS ===
#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <sys/resource.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

int main() {
    const char* json_str = R"RAWJSON([{"id": 0, "args": [5], "expected": 2}, {"id": 1, "args": [0], "expected": 0}, {"id": 2, "args": [15], "expected": 4}, {"id": 3, "args": [1023], "expected": 10}, {"id": 4, "args": [1024], "expected": 1}])RAWJSON";

    try {
        json cases = json::parse(json_str);
        json all_results = json::array();

        for (size_t i = 0; i < cases.size(); i++) {
            int id = cases[i]["id"];
            json args = cases[i]["args"];
            std::string expected;
            if (cases[i]["expected"].is_string()) {
                expected = cases[i]["expected"].get<std::string>();
            } else {
                expected = cases[i]["expected"].dump();
            }

            json test_res;
            test_res["id"] = id;

            try {
                struct rusage usage_start, usage_end;
                getrusage(RUSAGE_SELF, &usage_start);
                auto t_start = std::chrono::high_resolution_clock::now();

                json result_json;
                result_json = countSetBits(args[0]);

                auto t_end = std::chrono::high_resolution_clock::now();
                getrusage(RUSAGE_SELF, &usage_end);

                std::chrono::duration<double, std::milli> diff = t_end - t_start;
                double execMs = diff.count();
                double memKb = usage_end.ru_maxrss - usage_start.ru_maxrss;
                if (memKb < 0) memKb = 0;

                test_res["time_ms"] = execMs;
                test_res["mem_kb"] = memKb;

                std::string actual;
                if (result_json.is_string()) actual = result_json.get<std::string>();
                else actual = result_json.dump();

                // trim whitespace
                auto trim = [](std::string& s) {
                    size_t l = s.find_first_not_of(" \t\r\n");
                    size_t r = s.find_last_not_of(" \t\r\n");
                    if (l != std::string::npos) s = s.substr(l, r - l + 1);
                };
                trim(expected);
                trim(actual);

                if (actual == expected || result_json == cases[i]["expected"]) {
                    test_res["status"] = "pass";
                } else {
                    test_res["status"] = "fail";
                    test_res["expected"] = expected;
                    test_res["actual"] = actual;
                }
            } catch (const std::exception& ex) {
                test_res["status"] = "crash";
                test_res["error"] = ex.what();
            }
            all_results.push_back(test_res);
        }
        std::cout << all_results.dump() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Harness parse error: " << e.what() << std::endl;
        json fallback = json::array();
        json err_obj;
        err_obj["id"] = -1;
        err_obj["status"] = "crash";
        err_obj["error"] = "Harness setup failed";
        fallback.push_back(err_obj);
        std::cout << fallback.dump() << std::endl;
    }
    return 0;
}
