package apex.core;

import java.io.Serial;
import java.io.Serializable;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Sessão ativa do APEX.
 * Armazena histórico de execuções, mensagens e contexto conversacional.
 */
public class ApexSession implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    /**
     * Registro de cada ação executada durante a sessão.
     */
    private final List<SessionLog> logs = new ArrayList<>();

    /**
     * Mensagens trocadas durante a sessão (útil para handlers conversacionais).
     */
    private final List<String> conversation = new ArrayList<>();

    /**
     * Adiciona um registro de execução.
     */
    public void log(String intent, boolean success, String message) {
        logs.add(new SessionLog(
                Instant.now(),
                intent,
                success,
                message
        ));
    }

    /**
     * Adiciona uma mensagem ao contexto conversacional.
     */
    public void addMessage(String msg) {
        conversation.add(msg);
    }

    /**
     * Retorna o histórico de execuções.
     */
    public List<SessionLog> getLogs() {
        return List.copyOf(logs);
    }

    /**
     * Retorna o histórico de conversa.
     */
    public List<String> getConversation() {
        return List.copyOf(conversation);
    }

    /**
     * Registro individual de execução.
     */
    public record SessionLog(
            Instant timestamp,
            String intent,
            boolean success,
            String message
    ) implements Serializable {
        @Serial
        private static final long serialVersionUID = 20260303L;
    }
}