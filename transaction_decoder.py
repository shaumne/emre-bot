"""
Transaction decoder for CTF Exchange settlement monitoring.
Optional tool to decode and monitor on-chain settlement transactions.
"""

from typing import Optional, Dict, Any
from web3 import Web3
from web3.types import TxReceipt
from loguru import logger

from config import Config


# Minimal CTF Exchange ABI for fillOrder function
CTF_EXCHANGE_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "salt", "type": "uint256"},
                    {"internalType": "address", "name": "maker", "type": "address"},
                    {"internalType": "address", "name": "signer", "type": "address"},
                    {"internalType": "address", "name": "taker", "type": "address"},
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "uint256", "name": "makerAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "takerAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "expiration", "type": "uint256"},
                    {"internalType": "uint256", "name": "nonce", "type": "uint256"},
                    {"internalType": "uint256", "name": "feeRateBps", "type": "uint256"},
                    {"internalType": "enum Side", "name": "side", "type": "uint8"},
                    {"internalType": "enum SignatureType", "name": "signatureType", "type": "uint8"},
                    {"internalType": "bytes", "name": "signature", "type": "bytes"},
                ],
                "internalType": "struct Order",
                "name": "order",
                "type": "tuple",
            },
            {"internalType": "uint256", "name": "fillAmount", "type": "uint256"},
        ],
        "name": "fillOrder",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


class TransactionDecoder:
    """
    Decoder for CTF Exchange transactions.
    Useful for monitoring settlement transactions on-chain.
    """
    
    def __init__(self, config: Config):
        """
        Initialize transaction decoder.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        
        # Initialize CTF Exchange contract
        self.ctf_exchange = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.ctf_exchange_address),
            abi=CTF_EXCHANGE_ABI,
        )
        
        # Function signatures
        self.fill_order_signature = self.w3.keccak(
            text="fillOrder((uint256,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256,uint8,uint8,bytes),uint256)"
        ).hex()[:10]
        
        logger.info(f"TransactionDecoder initialized for {config.ctf_exchange_address}")
        logger.debug(f"fillOrder signature: {self.fill_order_signature}")
    
    def decode_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Decode a transaction by hash.
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            Decoded transaction data or None if not a fillOrder transaction
        """
        try:
            # Get transaction
            tx = self.w3.eth.get_transaction(tx_hash)
            
            if not tx:
                logger.warning(f"Transaction not found: {tx_hash}")
                return None
            
            # Check if it's to CTF Exchange
            if tx['to'].lower() != self.config.ctf_exchange_address.lower():
                logger.debug(
                    f"Transaction {tx_hash} is not to CTF Exchange "
                    f"(to: {tx['to']})"
                )
                return None
            
            # Check if it's a fillOrder call
            input_data = tx['input'].hex() if isinstance(tx['input'], bytes) else tx['input']
            
            if not input_data.startswith(self.fill_order_signature):
                logger.debug(
                    f"Transaction {tx_hash} is not a fillOrder call "
                    f"(signature: {input_data[:10]})"
                )
                return None
            
            # Decode function input
            try:
                func, params = self.ctf_exchange.decode_function_input(input_data)
                
                order = params['order']
                fill_amount = params['fillAmount']
                
                decoded = {
                    "tx_hash": tx_hash,
                    "from": tx['from'],
                    "to": tx['to'],
                    "function": func.fn_name,
                    "order": {
                        "salt": order[0],
                        "maker": order[1],
                        "signer": order[2],
                        "taker": order[3],
                        "tokenId": str(order[4]),
                        "makerAmount": order[5],
                        "takerAmount": order[6],
                        "expiration": order[7],
                        "nonce": order[8],
                        "feeRateBps": order[9],
                        "side": "BUY" if order[10] == 0 else "SELL",
                        "signatureType": order[11],
                    },
                    "fillAmount": fill_amount,
                    "blockNumber": tx.get('blockNumber'),
                    "gasPrice": tx.get('gasPrice'),
                }
                
                logger.info(f"Decoded transaction {tx_hash[:16]}...")
                logger.debug(f"  Maker: {decoded['order']['maker']}")
                logger.debug(f"  Token ID: {decoded['order']['tokenId'][:20]}...")
                logger.debug(f"  Side: {decoded['order']['side']}")
                logger.debug(f"  Fill Amount: {decoded['fillAmount']}")
                
                return decoded
                
            except Exception as e:
                logger.error(f"Failed to decode transaction input: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error decoding transaction {tx_hash}: {e}")
            return None
    
    def get_transaction_receipt(self, tx_hash: str) -> Optional[TxReceipt]:
        """
        Get transaction receipt.
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            Transaction receipt or None
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return receipt
        except Exception as e:
            logger.error(f"Failed to get transaction receipt {tx_hash}: {e}")
            return None
    
    def is_transaction_successful(self, tx_hash: str) -> bool:
        """
        Check if a transaction was successful.
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            True if successful, False otherwise
        """
        receipt = self.get_transaction_receipt(tx_hash)
        
        if not receipt:
            return False
        
        return receipt['status'] == 1
    
    def format_decoded_transaction(self, decoded: Dict[str, Any]) -> str:
        """
        Format decoded transaction for human-readable output.
        
        Args:
            decoded: Decoded transaction data
        
        Returns:
            Formatted string
        """
        order = decoded['order']
        
        # Convert amounts (assuming 6 decimals for USDC)
        maker_amount_usdc = order['makerAmount'] / 10**6
        taker_amount_usdc = order['takerAmount'] / 10**6
        fill_amount_usdc = decoded['fillAmount'] / 10**6
        
        output = f"""
Transaction: {decoded['tx_hash']}
Block: {decoded.get('blockNumber', 'Pending')}
From: {decoded['from']}
To: {decoded['to']}

Order Details:
  Maker: {order['maker']}
  Signer: {order['signer']}
  Taker: {order['taker']}
  Token ID: {order['tokenId']}
  Side: {order['side']}
  Maker Amount: ${maker_amount_usdc:.2f} USDC
  Taker Amount: ${taker_amount_usdc:.2f} USDC
  Fill Amount: ${fill_amount_usdc:.2f} USDC
  Fee Rate: {order['feeRateBps']} bps
  Signature Type: {order['signatureType']}
        """
        
        return output.strip()


def test_transaction_decoder():
    """Test transaction decoder with a known transaction."""
    from config import Config
    
    print("Testing TransactionDecoder...")
    
    # Create config
    try:
        config = Config()
    except Exception as e:
        print(f"⚠️  Config error: {e}")
        import os
        os.environ["POLY_PRIVATE_KEY"] = "test"
        config = Config()
    
    # Create decoder
    decoder = TransactionDecoder(config)
    print(f"✓ Decoder initialized")
    print(f"  CTF Exchange: {config.ctf_exchange_address}")
    print(f"  fillOrder signature: {decoder.fill_order_signature}")
    
    # Test with a sample transaction hash (replace with real one for testing)
    print("\nNote: To test with a real transaction:")
    print("1. Go to https://polygonscan.com/")
    print(f"2. Search for contract: {config.ctf_exchange_address}")
    print("3. Find a 'fillOrder' transaction")
    print("4. Copy the transaction hash and use decoder.decode_transaction(tx_hash)")
    
    print("\n✓ TransactionDecoder test completed!")


if __name__ == "__main__":
    test_transaction_decoder()


