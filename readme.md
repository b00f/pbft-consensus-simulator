# PBFT/Cheetah Consensus Implementation

This repository contains a Python implementation of the Practical Byzantine Fault Tolerance (PBFT) consensus algorithm and the Cheetah protocol.
It aims to provide simple implementations of both protocols to compare their network performance.

## How to Run

```bash
git clone https://github.com/yourusername/pbft-implementation.git
cd pbft-implementation
python3 main.py
```

## Customization

You can modify the following parameters in `main.py`:

- `N`: The total number of nodes.
- `f`: The maximum number of faulty nodes the protocol can tolerate.
- `delivery_threshold`: Sets a level of entropy for message delivery.

Please note that there is no anti-entropy mechanism for handling message loss.
Undelivered messages will not eventually be delivered, which might cause the protocol to halt in certain situations,
especially if the delivery threshold is set too high.

## License

This project is open source and available under the [MIT License](LICENSE).
