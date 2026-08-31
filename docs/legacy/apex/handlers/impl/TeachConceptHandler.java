package apex.handlers.impl;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.handlers.AbstractHandler;

import java.util.Map;

/**
 * Handler responsável por ensinar conceitos, explicar temas e gerar conteúdo educacional.
 * Ele utiliza o ApexKnowledge para registrar o que foi ensinado e o ApexSession para manter contexto.
 */
public class TeachConceptHandler extends AbstractHandler {

    public TeachConceptHandler(ApexContext context) {
        super(context);
    }

    @Override
    public String getIntentName() {
        return "teach-concept";
    }

    @Override
    public String getDescription() {
        return "Ensina um conceito solicitado pelo usuário, com explicação estruturada.";
    }

    @Override
    public String[] getRequiredParams() {
        return new String[] { "topic" };
    }

    @Override
    protected ActionResult performAction(Map<String, Object> params, ApexContext ctx) {

        String topic = params.get("topic").toString();

        // Registro de contexto conversacional
        ctx.session().addMessage("Usuário pediu explicação sobre: " + topic);

        // Geração da explicação (placeholder — será substituído por IA ou base de conhecimento)
        String explanation = """
                Aqui está uma explicação sobre o tópico solicitado:

                Tópico: %s

                Este é um conceito importante dentro do domínio de tecnologia e desenvolvimento.
                Para aprofundar, você pode pedir exemplos, analogias, exercícios ou aplicações práticas.
                """.formatted(topic);

        // Registro no conhecimento
        ctx.knowledge().addInsight("teach-concept", params, "explicado");

        return ActionResult.ok(
                "Conceito explicado com sucesso.",
                Map.of(
                        "topic", topic,
                        "explanation", explanation
                ),
                null
        );
    }
}