import tkinter as tk
from tkinter import ttk
from time import sleep
import uuid

from artnet.controller import ArtNetController, Universe
from light.light import nouveau_casino_offsets


class MapWizzard:
    def update_lights_with_selec(self, event) -> None:
        black = bytes([0] * 512)
        red = bytes([0xFF, 0, 0] * 170 + [0, 0])
        self.ctrl.set_all_universes(black, nouveau_casino_offsets)
        sleep(
            0.2
        )  # let the blackout packets be sent so that in case of udp reordering the below packet has a chance to be displayed
        selec = self.tree.selection()
        self.last_selec = selec
        univs = [self.items[item] for item in selec if item in self.items]
        for ip, port in univs:
            self.ctrl.set_universe(red, Universe(ip, port))
        self.ctrl.sync_universes()

    def __init__(self) -> None:
        with ArtNetController() as self.ctrl:
            self.last_selec = {}
            black = bytes([0] * 512)
            self.ctrl.set_all_universes(black, nouveau_casino_offsets)
            # Setup the root UI
            root = tk.Tk()
            root.title("PataShade visual mapper")
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)

            # Setup the Frames
            tree_frame = ttk.Frame(root, padding="3")
            tree_frame.grid(row=0, column=0, sticky=tk.NSEW)

            # Setup the Tree
            self.tree = ttk.Treeview(tree_frame, columns=["Offset"])
            self.tree.column("Offset", width=100, anchor="center")
            self.tree.heading("Offset", text="Offset")
            self.items = {}
            ips = {
                ip: uuid.uuid4()
                for ip in set([univ[0] for univ in nouveau_casino_offsets.keys()])
            }
            for ip, uid in ips.items():
                self.tree.insert("", "end", str(uid), text=ip, open=True, tags="ip")
            for univ, offset in nouveau_casino_offsets.items():
                ip_uid = ips[univ[0]]
                port_uuid = uuid.uuid4()
                self.items[str(port_uuid)] = univ
                self.tree.insert(
                    str(ip_uid),
                    "end",
                    str(port_uuid),
                    text=f"Universe {univ[1]}",
                    value=offset,
                    tags=["univ"],
                )  # type: ignore
            self.tree.tag_bind(
                "univ", "<<TreeviewSelect>>", self.update_lights_with_selec
            )

            # json_tree(tree, "", data)
            self.tree.pack(fill=tk.BOTH, expand=1)

            # Limit windows minimum dimensions
            root.update_idletasks()
            root.minsize(600, 800)
            root.mainloop()
            print(self.last_selec)
            selec = self.last_selec
            univs = [self.items[item] for item in selec if item in self.items]
            for ip, port in univs:
                print(Universe(ip, port))

    print("bye")


if __name__ == "__main__":
    MapWizzard()
