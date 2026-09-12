

class Solution {
public int countSetBits(int n) {
    if (n < 0) {
        throw new IllegalArgumentException("Negative numbers are not valid inputs.");
    }
    int count = 0;
    while (n > 0) {
        count += n & 1;
        n >>>= 1;
    }
    return count;
}
}

// === INJECTED BY SANDBOX ===
class SandboxRunner {
    public static void main(String[] args) {
        String jsonTests = "[{\"id\": 0, \"args\": [5], \"expected\": 2}, {\"id\": 1, \"args\": [0], \"expected\": 0}, {\"id\": 2, \"args\": [15], \"expected\": 4}, {\"id\": 3, \"args\": [1023], \"expected\": 10}, {\"id\": 4, \"args\": [1024], \"expected\": 1}]";
        org.json.JSONArray allResults = new org.json.JSONArray();
        try {
            org.json.JSONArray cases = new org.json.JSONArray(jsonTests);
            for (int i = 0; i < cases.length(); i++) {
                org.json.JSONObject tc = cases.getJSONObject(i);
                int id = tc.getInt("id");
                org.json.JSONArray tcArgs = tc.getJSONArray("args");
                String expected = tc.get("expected").toString().trim();
                
                org.json.JSONObject res = new org.json.JSONObject();
                res.put("id", id);
                
                try {
                    java.lang.reflect.Method solveMethod = null;
                    for (java.lang.reflect.Method m : Solution.class.getDeclaredMethods()) {
                        if (java.lang.reflect.Modifier.isPublic(m.getModifiers()) && !m.getName().equals("main")) {
                            solveMethod = m;
                            break;
                        }
                    }
                    if (solveMethod == null) throw new RuntimeException("No public method found in Solution.");
                    
                    Class<?>[] paramTypes = solveMethod.getParameterTypes();
                    Object[] parsedArgs = new Object[paramTypes.length];
                    for (int j = 0; j < paramTypes.length; j++) {
                        parsedArgs[j] = convertJson(tcArgs.get(j), paramTypes[j]);
                    }
                    
                    Object instance = null;
                    if (!java.lang.reflect.Modifier.isStatic(solveMethod.getModifiers())) {
                        instance = Solution.class.getDeclaredConstructor().newInstance();
                    }
                    
                    Runtime rt = Runtime.getRuntime();
                    rt.gc(); 
                    long startMem = rt.totalMemory() - rt.freeMemory();
                    long startTime = System.nanoTime();
                    
                    Object result = solveMethod.invoke(instance, parsedArgs);
                    
                    long endTime = System.nanoTime();
                    long endMem = rt.totalMemory() - rt.freeMemory();
                    
                    double execMs = (endTime - startTime) / 1000000.0;
                    double memKb = Math.max(0, endMem - startMem) / 1024.0;
                    
                    res.put("time_ms", execMs);
                    res.put("mem_kb", memKb);
                    
                    String actual = convertResult(result).trim();
                    if (actual.equals(expected)) {
                        res.put("status", "pass");
                    } else {
                        res.put("status", "fail");
                        res.put("expected", expected);
                        res.put("actual", actual);
                    }
                } catch (Exception e) {
                    res.put("status", "crash");
                    String msg = e.getCause() != null ? e.getCause().toString() : e.toString();
                    res.put("error", msg);
                }
                
                allResults.put(res);
            }
        } catch (Exception e) {
            org.json.JSONObject err = new org.json.JSONObject();
            err.put("id", -1);
            err.put("status", "crash");
            err.put("error", "Harness error: " + e.getMessage());
            allResults.put(err);
        }
        System.out.println(allResults.toString());
    }
    
    private static Object convertJson(Object jsonVal, Class<?> targetType) throws Exception {
        if (targetType == int.class || targetType == Integer.class) return ((Number)jsonVal).intValue();
        if (targetType == long.class || targetType == Long.class) return ((Number)jsonVal).longValue();
        if (targetType == double.class || targetType == Double.class) return ((Number)jsonVal).doubleValue();
        if (targetType == boolean.class || targetType == Boolean.class) return (Boolean)jsonVal;
        if (targetType == String.class) return jsonVal.toString();
        
        if (targetType.isArray() && jsonVal instanceof org.json.JSONArray) {
            org.json.JSONArray arr = (org.json.JSONArray) jsonVal;
            Class<?> compType = targetType.getComponentType();
            Object res = java.lang.reflect.Array.newInstance(compType, arr.length());
            for (int i = 0; i < arr.length(); i++) {
                java.lang.reflect.Array.set(res, i, convertJson(arr.get(i), compType));
            }
            return res;
        }
        
        if (java.util.List.class.isAssignableFrom(targetType) && jsonVal instanceof org.json.JSONArray) {
            org.json.JSONArray arr = (org.json.JSONArray) jsonVal;
            java.util.List<Object> list = new java.util.ArrayList<>();
            for (int i = 0; i < arr.length(); i++) {
                Object val = arr.get(i);
                if (val instanceof Number) val = ((Number)val).intValue();
                list.add(val);
            }
            return list;
        }
        
        return jsonVal;
    }
    
    private static String convertResult(Object res) {
        if (res == null) return "null";
        if (res.getClass().isArray()) {
            StringBuilder b = new StringBuilder("[");
            int len = java.lang.reflect.Array.getLength(res);
            for (int i = 0; i < len; i++) {
                if (i > 0) b.append(", ");
                b.append(convertResult(java.lang.reflect.Array.get(res, i)));
            }
            b.append("]");
            return b.toString();
        }
        return res.toString();
    }
}
