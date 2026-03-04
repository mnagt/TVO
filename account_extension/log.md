UncaughtPromiseError > OwlError

Uncaught Promise > An error occured in the owl lifecycle (see this Error's "cause" property)

Occured on stage.tvo-oil.com on 2026-02-24 09:04:00 GMT

OwlError: An error occured in the owl lifecycle (see this Error's "cause" property)
    Error: An error occured in the owl lifecycle (see this Error's "cause" property)
        at handleError (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:972:101)
        at App.handleError (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:1631:29)
        at Fiber._render (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:997:19)
        at Fiber.render (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:995:6)
        at ComponentNode.initiateRender (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:1066:47)

Caused by: EvalError: Can not evaluate python expression: (bool(not sale_info_enabled))
    Error: Name 'sale_info_enabled' is not defined
    EvalError: Can not evaluate python expression: (bool(not sale_info_enabled))
    Error: Name 'sale_info_enabled' is not defined
        at evaluateExpr (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:3373:54)
        at evaluateBooleanExpr (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:3376:8)
        at ListRenderer.evalColumnInvisible (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:9491:45)
        at https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:9402:9
        at Array.filter (<anonymous>)
        at ListRenderer.getActiveColumns (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:9400:47)
        at ListRenderer.<anonymous> (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:9393:2024)
        at node.renderFn (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:1115:198)
        at Fiber._render (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:996:96)
        at Fiber.render (https://stage.tvo-oil.com/web/assets/25eee15/web.assets_web.min.js:995:6)