#include <iostream>
#include <nlohmann/json.hpp>
using json = nlohmann::json;
int fib(int n) { return n; }
int main() { json j = 5; int res = fib(j); std::cout << res; return 0; }
