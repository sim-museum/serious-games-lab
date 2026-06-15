module JuliaMotorMTK

# Data ingestion (no heavy deps) — load + read iRacing .ibt telemetry and pull
# model parameters from its CarSetup YAML.
include("ibt.jl");   using .IBT
include("setup.jl"); using .Setup

export IBT, Setup

# The acausal ModelingToolkit components (connectors, Tyre, Corner, powertrain,
# full Vehicle assembly) are added under src/components/ as they come online —
# see README.md §2 for the component inventory.

end # module
