#!/usr/bin/env python3
"""
End-to-end test for MyVoiceTranslator WebSocket endpoint.
Tests the core HTTP and WebSocket endpoints.
"""

import asyncio
import json
import sys
import websockets
import aiohttp


async def test_websocket_basic(port=8004):
    """Test basic WebSocket connectivity and ping/pong."""
    ws_url = f"ws://localhost:{port}/transcribe"
    
    print(f"Connecting to {ws_url}...")
    
    try:
        async with websockets.connect(ws_url) as ws:
            print("✓ WebSocket connected")
            
            # Test ping/pong
            await ws.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(response)
            assert data.get("type") == "status", f"Expected status, got {data}"
            print(f"✓ Ping/pong works: {data.get('message', 'OK')}")
            
            # Test that we can receive server status messages
            # (pipeline initialization status, etc.)
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"✓ Received server message: {data.get('type', 'unknown')}")
            except asyncio.TimeoutError:
                print("⚠ No additional messages (server may still be initializing)")
            
            return True
            
    except ConnectionRefusedError:
        print("✗ Connection refused - is the server running on port 8004?")
        return False
    except Exception as e:
        print(f"✗ WebSocket error: {e}")
        return False


async def test_health_endpoint(port=8004):
    """Test HTTP health endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://localhost:{port}/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ Health endpoint: {data}")
                    return True
                else:
                    print(f"✗ Health endpoint returned {resp.status}")
                    return False
    except Exception as e:
        print(f"✗ Health endpoint error: {e}")
        return False


async def test_switch_to_tui_endpoint(port=8004):
    """Test /api/switch-to-tui endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://localhost:{port}/api/switch-to-tui") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ Switch-to-TUI endpoint: {data}")
                    return True
                else:
                    print(f"✗ Switch-to-TUI returned {resp.status}")
                    return False
    except Exception as e:
        print(f"✗ Switch-to-TUI error: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 50)
    print("MyVoiceTranslator E2E WebSocket Tests")
    print("=" * 50)
    print()
    
    # Test WebSocket FIRST (before switch-to-tui shuts down server)
    print("Testing WebSocket endpoint...")
    ws_ok = await test_websocket_basic(8004)
    print()
    
    # Test health endpoint
    print("Testing HTTP endpoints...")
    health_ok = await test_health_endpoint(8004)
    print()
    
    switch_ok = await test_switch_to_tui_endpoint(8004)
    print()
    
    print("=" * 50)
    if health_ok and switch_ok and ws_ok:
        print("All tests PASSED ✓")
        return 0
    else:
        print("Some tests FAILED ✗")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))