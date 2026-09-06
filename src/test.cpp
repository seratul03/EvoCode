#include <iostream>
#include <nlohmann/json.hpp>
using json = nlohmann::json;
int fib(int n) { return n; }
int main() { json args = json::array({5}); json result_json = fib(args[0]); std::cout << result_json; return 0; }
