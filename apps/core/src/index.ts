import { buildServer } from "./server.js";

const { app, config } = await buildServer();

app.log.info(
  `Nova core starting on pipe ${config.pipePath}. Export NOVA_AUTH_TOKEN for client use.`
);
app.log.info(`NOVA_AUTH_TOKEN=${config.authToken}`);

await app.listen({
  path: config.pipePath
});

