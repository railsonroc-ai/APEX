package apex.memory;

import java.io.Serial;
import java.io.Serializable;
import java.time.Instant;
import java.util.*;

/**
 * Sistema de conhecimento do APEX.
 * Armazena insights, entidades e metadados gerados durante a execução.
 */
public class ApexKnowledge implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    /**
     * Lista de insights registrados.
     */
    private final List<Insight> insights = new ArrayList<>();

    /**
     * Entidades registradas (ex: módulos, serviços, arquivos criados).
     */
    private final Map<String, List<EntityRecord>> entities = new HashMap<>();

    /**
     * Registra um insight simples.
     */
    public void addInsight(String category, Map<String, Object> data, String note) {
        insights.add(new Insight(
                Instant.now(),
                category,
                Map.copyOf(data),
                note
        ));
    }

    /**
     * Registra uma entidade criada ou manipulada pelo APEX.
     */
    public void registerEntity(String type, String name, String path, Map<String, Object> metadata) {
        entities.computeIfAbsent(type, k -> new ArrayList<>())
                .add(new EntityRecord(
                        Instant.now(),
                        name,
                        path,
                        Map.copyOf(metadata)
                ));
    }

    public List<Insight> getInsights() {
        return List.copyOf(insights);
    }

    public Map<String, List<EntityRecord>> getEntities() {
        return Collections.unmodifiableMap(entities);
    }

    /**
     * Registro de insight.
     */
    public record Insight(
            Instant timestamp,
            String category,
            Map<String, Object> data,
            String note
    ) implements Serializable {
        @Serial
        private static final long serialVersionUID = 20260303L;
    }

    /**
     * Registro de entidade.
     */
    public record EntityRecord(
            Instant timestamp,
            String name,
            String path,
            Map<String, Object> metadata
    ) implements Serializable {
        @Serial
        private static final long serialVersionUID = 20260303L;
    }
}