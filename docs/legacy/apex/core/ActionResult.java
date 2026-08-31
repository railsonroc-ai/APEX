package apex.core;

import java.io.Serial;
import java.io.Serializable;
import java.util.Map;

/**
 * Resultado padronizado de qualquer ação executada por um handler.
 * Contém mensagem, dados e erro opcional.
 */
public class ActionResult implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final String message;
    private final Map<String, Object> data;
    private final String error;

    public ActionResult(String message, Map<String, Object> data, String error) {
        this.message = message;
        this.data = data == null ? Map.of() : Map.copyOf(data);
        this.error = error;
    }

    public static ActionResult ok(String message, Map<String, Object> data, String error) {
        return new ActionResult(message, data, error);
    }

    public static ActionResult fail(String message, String error) {
        return new ActionResult(message, Map.of(), error);
    }

    public String message() {
        return message;
    }

    public Map<String, Object> data() {
        return data;
    }

    public String error() {
        return error;
    }

    public boolean isSuccess() {
        return error == null;
    }
}