# Synthetic Data

The generator creates deterministic synthetic D2C order data for the current COD/RTO foundation milestone.

Generate the default dataset:

```bash
python data/generate.py --rows 10000 --seed 42
```

The output is written to:

```text
data/generated/orders.csv
```

Generated CSV files are ignored by Git. The generator and validation code remain tracked.

The data is synthetic and does not contain real customer information. It includes controlled pincode risk groups, order history, payment method, product category, and observed `rto_outcome` labels for future model training experiments.

