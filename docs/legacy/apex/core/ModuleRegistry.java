package apex.core;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

public class ModuleRegistry {

    private final Map<String, ModuleInfo> modules = new ConcurrentHashMap<>();

    public void register(ModuleInfo module) {
        modules.put(module.name(), module);
    }

    public Optional<ModuleInfo> find(String name) {
        return Optional.ofNullable(modules.get(name));
    }

    public List<ModuleInfo> list() {
        return new ArrayList<>(modules.values());
    }

    public void remove(String name) {
        modules.remove(name);
    }

    public void clear() {
        modules.clear();
    }
}

record ModuleInfo(
    String name,
    String path,
    String description
) {}
