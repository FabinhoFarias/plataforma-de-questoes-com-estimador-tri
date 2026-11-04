const fs = require("fs");
const path = require("path");

const filePath = path.join(__dirname, "../docs/produto/MATRIZ_REQUISITOS.md");

try {
  const content = fs.readFileSync(filePath, "utf-8");
  const regexRequisitos = /(RF-|RNF-)\d+/g;
  const idsEncontrados = content.match(regexRequisitos) || [];
  const totalRequisitos = idsEncontrados.length;
  const concluidos = (content.match(/✅/g) || []).length;
  const porcentagem =
    totalRequisitos > 0 ? Math.round((concluidos / totalRequisitos) * 100) : 0;
  const novaUrl = `https://geps.dev/progress/${porcentagem}`;
  const contentAtualizado = content.replace(
    /https:\/\/geps\.dev\/progress\/\d+/,
    novaUrl,
  );

  fs.writeFileSync(filePath, contentAtualizado);
  console.log(
    `📊 Progresso: ${porcentagem}% (${concluidos} de ${totalRequisitos} requisitos finalizados).`,
  );
} catch (err) {
  console.error("Erro ao ler o arquivo:", err);
  process.exitCode = 1;
}
