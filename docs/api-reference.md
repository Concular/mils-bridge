---
hide:
  - toc
---

# OpenAPI contract

The contract a peer node implements against this bridge, and that this bridge
serves under `/rest/*`. The prose that goes with it — which operations exist,
what each answers, and how a peer authenticates — is
[The `/rest` API](mils-internal-api.md).

[Download `mils-internal.yaml`](../spec/mils-internal.yaml){ .md-button }
[View on GitHub](https://github.com/Concular/mils-bridge/blob/main/spec/mils-internal.yaml){ .md-button }

<div id="redoc-container" class="bridge-redoc"></div>

<script src="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js"></script>
<script>
  // The spec is published beside the pages by docs-site/hooks.py.
  Redoc.init(
    new URL('../spec/mils-internal.yaml', window.location.href).href,
    {
      hideDownloadButton: true,
      expandResponses: '200,201',
      scrollYOffset: '.md-header',
    },
    document.getElementById('redoc-container'),
  );
</script>

<style>
  /* Let Redoc's three-pane layout use the full content width. */
  .md-content__inner:has(.bridge-redoc) { max-width: none; }
  .bridge-redoc { margin: 1.5rem -0.8rem 0; background: #fff; border-radius: 4px; }
</style>
