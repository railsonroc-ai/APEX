package apex.core;

import apex.handlers.AbstractHandler;

import java.io.Serial;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Registro de intents disponíveis no agente.
 */
public class IntentRegistry implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260304L;

    private final Map<String, IntentInfo> intents = new ConcurrentHashMap<>();
    private final transient Map<String, AbstractHandler> handlers = new ConcurrentHashMap<>();

    public void register(AbstractHandler handler) {
        Objects.requireNonNull(handler, "handler não pode ser nulo");

        intents.put(
                handler.getIntentName(),
                new IntentInfo(handler.getIntentName(), handler.getDescription())
        );
        handlers.put(handler.getIntentName(), handler);
    }

    public void registerAlias(String alias, AbstractHandler handler) {
        Objects.requireNonNull(alias, "alias não pode ser nulo");
        Objects.requireNonNull(handler, "handler não pode ser nulo");

        intents.put(alias, new IntentInfo(alias, handler.getDescription()));
        handlers.put(alias, handler);
    }

    public Optional<IntentInfo> find(String name) {
        if (name == null || name.isBlank()) {
            return Optional.empty();
        }
        return Optional.ofNullable(intents.get(name));
    }

    public ActionResult execute(String intentName, Map<String, Object> params) {
        AbstractHandler handler = handlers.get(intentName);
        if (handler == null) {
            return ActionResult.fail(
                    "Intent '" + intentName + "' não encontrada.",
                    "Intent '" + intentName + "' não encontrada."
            );
        }
        return handler.execute(params == null ? Map.of() : params);
    }

    public List<IntentInfo> list() {
        return intents.values().stream()
                .sorted(Comparator.comparing(IntentInfo::name))
                .collect(ArrayList::new, ArrayList::add, ArrayList::addAll);
    }

    public record IntentInfo(String name, String description) implements Serializable {
        @Serial
        private static final long serialVersionUID = 20260304L;
    }
}
