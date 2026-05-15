# Root Guessing Reference

Use when a WBP `WidgetTree` exists but Python cannot read `RootWidget` or `get_all_widgets()`.

## Candidate Extraction

Scan the corresponding `.uasset` file as bytes and extract ASCII-ish names. Keep names containing widget-like tokens:

- `Root`, `Canvas`, `Panel`, `Overlay`, `InvalidationBox`
- `Button`, `Image`, `Border`, `Box`, `Progress`, `Text`, `ScaleBox`, `SizeBox`

Reject obvious class/graph names such as `Default__*`, `MovieScene*`, `DTransformTrack*`, `ExecuteUbergraph*`, slot class names, and plain widget class names like `CanvasPanel`.

## Candidate Selection

Try candidates independently through full Editor Python. For each candidate:

1. Find it through `WidgetTree.find_widget`, `find_widget_by_name`, inner-object lookup, or `WidgetTree.<Name>`/`WidgetTree/<Name>` object paths.
2. Walk children with `get_children_count` / `get_child_at`, plus content getters like `get_content`.
3. Count reachable widgets.

Select the candidate with the largest reachable subtree. For ties, prefer container classes before leaves:

```text
InvalidationBox, CanvasPanel, Overlay > other Panel/Box > Button > Image > other
```

## Known Results From Development

```text
BP_BattleScreen             CanvasPanel_366      84
BP_FireButtonWithReload     InvalidationBox_0    14
BP_UltimateButton           InvalidationBox_0    32
BP_TurnoverButton           ProgressOverlay       7
BP_SniperButton             InvalidationBox_0     5
BP_BaseUIButton             ButtonBorder          3
```

One-widget results may still be valid for small widgets, but should be treated as suspicious for complex controls.
