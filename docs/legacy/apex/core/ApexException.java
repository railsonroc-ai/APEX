package apex.core;

import java.io.Serial;
import java.io.Serializable;

/**
 * Exceção padronizada do APEX.
 * Contém tipo, código, chave de mensagem e detalhes adicionais.
 */
public class ApexException extends RuntimeException implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final Tipo tipo;
    private final String codigo;
    private final String chaveMensagem;
    private final String detalhe;

    public ApexException(Tipo tipo, String codigo, String chaveMensagem, String detalhe) {
        super(chaveMensagem + " - " + detalhe);
        this.tipo = tipo;
        this.codigo = codigo;
        this.chaveMensagem = chaveMensagem;
        this.detalhe = detalhe;
    }

    public Tipo getTipo() {
        return tipo;
    }

    public String getCodigo() {
        return codigo;
    }

    public String getChaveMensagem() {
        return chaveMensagem;
    }

    public String getDetalhe() {
        return detalhe;
    }

    /**
     * Tipos padronizados de erro no APEX.
     */
    public enum Tipo {
        PARAMETRO_INVALIDO,
        HANDLER_NAO_ENCONTRADO,
        EXECUCAO_FALHOU,
        SISTEMA,
        ROLLBACK_FALHOU
    }
}