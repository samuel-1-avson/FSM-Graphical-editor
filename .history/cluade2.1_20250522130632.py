import sys
import os
import tempfile
import subprocess
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer
)
import math


# --- Configuration ---
APP_VERSION = "1.1"
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Utility Functions ---
def get_standard_icon(standard_pixmap_enum_value, fallback_text=None):
    # standard_pixmap_enum_value is now the actual enum value (e.g., QStyle.SP_FileIcon)
    icon = QIcon() # Default to empty icon
    try:
        # This call itself should handle invalid enum values gracefully by returning a null icon.
        icon = QApplication.style().standardIcon(standard_pixmap_enum_value)
    except Exception as e: # Catch any unexpected error during icon retrieval
        print(f"Warning: Error getting standard icon for enum value {standard_pixmap_enum_value}: {e}")
        icon = QIcon() # Ensure icon is QIcon instance
    
    if icon.isNull():
        if fallback_text:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, fallback_text[:2])
            painter.end()
            return QIcon(pixmap)
        else:
            return QIcon() # Return empty icon if no text fallback and standard icon is null
    return icon

# --- MATLAB Connection Handling ---
class MatlabConnection(QObject):
    """Class to handle MATLAB connectivity"""
    connectionStatusChanged = pyqtSignal(bool, str)  # success, message
    simulationFinished = pyqtSignal(bool, str, str)      # success, message, data (model_path or general message)
    codeGenerationFinished = pyqtSignal(bool, str, str)  # success, message, output_dir

    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False
        self._active_threads = [] # To keep track of running threads

    def set_matlab_path(self, path):
        """Set the path to MATLAB executable and test basic validity."""
        self.matlab_path = path
        if path and os.path.exists(path) and (os.access(path, os.X_OK) or path.endswith('.exe')): # Basic check
            self.connected = True
            self.connectionStatusChanged.emit(True, f"MATLAB path set: {path}")
            return True
        else:
            self.connected = False
            self.matlab_path = ""
            self.connectionStatusChanged.emit(False, "MATLAB path is invalid or not executable.")
            return False

    def test_connection(self):
        """Actively test MATLAB connection by running a simple command."""
        if not self.connected or not self.matlab_path:
            self.connectionStatusChanged.emit(False, "MATLAB path not set.")
            return False

        try:
            process = subprocess.run(
                [self.matlab_path, "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS')"],
                capture_output=True, text=True, timeout=15, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if "MATLAB_CONNECTION_TEST_SUCCESS" in process.stdout:
                self.connectionStatusChanged.emit(True, "MATLAB connection successful.")
                return True
            else:
                self.connected = False # Downgrade status if test fails
                error_msg = process.stderr or "Unexpected output from MATLAB."
                self.connectionStatusChanged.emit(False, f"MATLAB connection test failed: {error_msg}")
                return False
        except subprocess.TimeoutExpired:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB connection test timed out.")
            return False
        except subprocess.CalledProcessError as e:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"MATLAB error during test: {e.stderr or e.stdout or str(e)}")
            return False
        except FileNotFoundError:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB executable not found at the specified path.")
            return False
        except Exception as e:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"An unexpected error occurred during MATLAB test: {str(e)}")
            return False


    def detect_matlab(self):
        """Try to auto-detect MATLAB installation."""
        paths = []
        if sys.platform == 'win32':
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(os.path.join(program_files, 'MATLAB', v, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin':
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(f'/Applications/MATLAB_{v}.app/bin/matlab')
        else:  # Linux
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(f'/usr/local/MATLAB/{v}/bin/matlab')

        for path in paths:
            if os.path.exists(path):
                self.set_matlab_path(path)
                return True
        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed.")
        return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected.", "")
            return

        temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
        script_file = os.path.join(temp_dir, "matlab_script.m")
        with open(script_file, 'w') as f:
            f.write(script_content)

        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run_command)
        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        self._active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)
        
        thread.start()


    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "") 
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')

        script_lines = [
            f"% Auto-generated Simulink model script for {model_name}",
            f"disp('Starting Simulink model generation for {model_name}...');",
            f"modelName = '{model_name}';",
            f"outputModelPath = '{slx_file_path}';",
            "try",
            "    if exist(outputModelPath, 'file'), delete(outputModelPath); end", 
            "    if bdIsLoaded(modelName), close_system(modelName, 0); end",
            "    new_system(modelName);",
            "    open_system(modelName);",
            "    sfChart = Stateflow.Chart(modelName);",
            "    sfChart.Name = 'BrainStateMachineChart';",
            "    stateHandles = containers.Map('KeyType','char','ValueType','any');"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") 
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}";
            s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe))
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe


            script_lines.extend([
                f"{s_id_matlab_safe} = Stateflow.State(sfChart);",
                f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                f"{s_id_matlab_safe}.Position = [{state['x']/5}, {state['y']/5}, {state['width']/5}, {state['height']/5}];",
                f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"
            ])
            if state.get('is_initial', False):
                script_lines.append(f"defaultTransition_{i} = Stateflow.Transition(sfChart);")
                script_lines.append(f"defaultTransition_{i}.Destination = {s_id_matlab_safe};")
                script_lines.append(f"defaultTransition_{i}.Source = [];")

        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")
            t_label_matlab = trans['label'].replace("'", "''") if trans.get('label') else ''
            
            script_lines.extend([
                f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"    t{i} = Stateflow.Transition(sfChart);",
                f"    t{i}.Source = stateHandles('{src_name_matlab}');",
                f"    t{i}.Destination = stateHandles('{dst_name_matlab}');"
            ])
            if t_label_matlab:
                script_lines.append(f"    t{i}.LabelString = '{t_label_matlab}';")
            script_lines.append("else")
            script_lines.append(f"    disp(['Warning: Could not create transition from {src_name_matlab} to {dst_name_matlab} - state not found.']);")
            script_lines.append("end")


        script_lines.extend([
            "    disp(['Attempting to save model to: ', outputModelPath]);",
            "    save_system(modelName, outputModelPath);",
            "    close_system(modelName, 0);",
            "    disp(['Simulink model saved to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);", 
            "catch e",
            "    disp(['Error during Simulink model generation: ', getReport(e, 'extended')]);",
            "    if bdIsLoaded(modelName), close_system(modelName, 0); end",  
            "    rethrow(e);",
            "end"
        ])
        
        script_content = "\n".join(script_lines)
        self._run_matlab_script(script_content, self.simulationFinished, "Model generation")
        return True 

    def run_simulation(self, model_path, sim_time=10):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "")
            return False
        if not os.path.exists(model_path):
            self.simulationFinished.emit(False, f"Model file not found: {model_path}", "")
            return False

        model_path_matlab = model_path.replace('\\', '/')
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        script_content = f"""
        disp('Starting simulation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        try
            load_system(modelPath);
            set_param(modelName, 'StopTime', '{sim_time}');
            disp(['Simulating model: ', modelName, ' for ', num2str({sim_time}), ' seconds.']);
            simOut = sim(modelName);
            disp('Simulation completed successfully.');
            fprintf('MATLAB_SCRIPT_SUCCESS:Simulation finished for %s.\\n', modelName);
        catch e
            disp(['Simulation error: ', getReport(e, 'extended')]);
            if bdIsLoaded(modelName), close_system(modelName, 0); end 
            rethrow(e); 
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end
        """
        self._run_matlab_script(script_content, self.simulationFinished, "Simulation")
        return True


    def generate_code(self, model_path, language="C++", output_dir_base=None):
        if not self.connected:
            self.codeGenerationFinished.emit(False, "MATLAB not connected", "")
            return False

        model_path_matlab = model_path.replace('\\', '/')
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        
        if not output_dir_base:
            output_dir_base = os.path.dirname(model_path)
        output_dir_matlab = os.path.join(output_dir_base, f"{model_name}_codegen").replace('\\', '/')


        script_content = f"""
        disp('Starting code generation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        outputDirBaseForMatlab = '{output_dir_matlab}';
        
        try
            load_system(modelPath);
            
            set_param(modelName,'SystemTargetFile','ert.tlc');
            set_param(modelName,'GenerateMakefile','on');

            cfg = getActiveConfigSet(modelName);
            if strcmpi('{language}', 'C++')
                set_param(cfg, 'TargetLang', 'C++');
                disp('Configured for C++ code generation.');
            else
                set_param(cfg, 'TargetLang', 'C');
                disp('Configured for C code generation.');
            end
            set_param(cfg, 'GenerateReport', 'on');
            set_param(cfg, 'GenCodeOnly', 'on'); 
            
            codeGenFolder = fullfile(outputDirBaseForMatlab); 
            if ~exist(codeGenFolder, 'dir')
               mkdir(codeGenFolder);
            end
            
            cs = getActiveConfigSet(modelName);
            set_param(cs.getComponent('Code Generation'),'TargetLangStandard', 'C++11 (ISO)');
            set_param(cs.getComponent('Code Generation'),'CodeInterfacePackaging', 'Reusable function');
            
            disp(['Code generation output target directory: ', codeGenFolder]);
            slbuild(modelName, 'StandaloneRTWTarget', 'GenCodeOnly', true, 'CodeGenerationFolder', codeGenFolder);
            disp('Code generation command (slbuild) executed.');
            
            actualCodeDir = codeGenFolder; 

            disp(['Code generation successful. Code and report expected in: ', actualCodeDir]);
            fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir); 
        catch e
            disp(['Code generation error: ', getReport(e, 'extended')]);
            if bdIsLoaded(modelName), close_system(modelName, 0); end 
            rethrow(e);
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end
        """
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation")
        return True

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) 

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.original_signal = original_signal
        self.success_message_prefix = success_message_prefix

    def run_command(self):
        output_data_for_signal = ""
        success = False
        message = ""
        try:
            cmd = [self.matlab_path, "-batch", f"run('{self.script_file}')"]
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  
                check=False,   
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 
            )

            if process.returncode == 0:
                if "MATLAB_SCRIPT_SUCCESS" in process.stdout:
                    success = True
                    for line in process.stdout.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data_for_signal and self.success_message_prefix != "Simulation":
                         message += f" Output at: {output_data_for_signal}"
                    elif output_data_for_signal and self.success_message_prefix == "Simulation":
                        message = output_data_for_signal

                else: 
                    success = False 
                    message = f"{self.success_message_prefix} finished, but success marker not found. MATLAB output: {process.stdout[:200]}"
                    if process.stderr:
                        message += f"\nMATLAB stderr: {process.stderr[:200]}"
            else: 
                success = False
                error_output = process.stderr or process.stdout
                message = f"{self.success_message_prefix} failed. MATLAB Error (Return Code {process.returncode}): {error_output[:500]}"
            
            self.original_signal.emit(success, message, output_data_for_signal if success else "")

        except subprocess.TimeoutExpired:
            message = f"{self.success_message_prefix} timed out after 5 minutes."
            self.original_signal.emit(False, message, "")
        except FileNotFoundError:
            message = "MATLAB executable not found."
            self.original_signal.emit(False, message, "")
        except Exception as e:
            message = f"{self.success_message_prefix} worker error: {str(e)}"
            self.original_signal.emit(False, message, "")
        finally:
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    os.rmdir(os.path.dirname(self.script_file))
                except OSError as e:
                    print(f"Warning: Could not clean up temp script: {e}") 
            self.finished_signal.emit(success, message, output_data_for_signal)


# --- Draggable Toolbox Buttons ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, style_sheet, parent=None):
        super().__init__(text, parent)
        self.mime_type = mime_type
        self.setFixedSize(120, 40)
        self.setStyleSheet(style_sheet + " border-radius: 5px;")
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        mime_data.setData(self.mime_type, b"1")
        drag.setMimeData(mime_data)

        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        drag.exec_(Qt.CopyAction)


# --- Graphics Items ---
class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1
    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False):
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self._text_color = Qt.black
        self._font = QFont("Arial", 10)

        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(173, 216, 230)))
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges |
                      QGraphicsItem.ItemIsFocusable)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 5, 5)

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        painter.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            painter.setBrush(Qt.black)
            painter.setPen(QPen(Qt.black, 2))
            start_x = self.rect().left() - 25
            start_y = self.rect().center().y()
            end_x = self.rect().left()
            end_y = self.rect().center().y()
            
            line = QLineF(QPointF(start_x, start_y), QPointF(end_x, end_y))
            painter.drawLine(line)
            
            angle_rad = math.atan2(line.dy(), line.dx())
            arrow_size = 10
            
            p2_x = line.p2().x() - arrow_size * math.cos(angle_rad + math.pi / 6)
            p2_y = line.p2().y() - arrow_size * math.sin(angle_rad + math.pi / 6)
            p3_x = line.p2().x() - arrow_size * math.cos(angle_rad - math.pi / 6)
            p3_y = line.p2().y() - arrow_size * math.sin(angle_rad - math.pi / 6)

            painter.setBrush(Qt.black)
            painter.drawPolygon(QPolygonF([line.p2(), QPointF(p2_x, p2_y), QPointF(p3_x, p3_y)]))


        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            inner_rect = self.rect().adjusted(5, 5, -5, -5)
            painter.drawRoundedRect(inner_rect, 3, 3)

        if self.isSelected():
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final
        }
    
    def set_text(self, text):
        self.text_label = text
        self.update()

    def set_properties(self, name, is_initial, is_final):
        self.text_label = name
        self.is_initial = is_initial
        self.is_final = is_final
        self.update()

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, text=""):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.text_label = text
        self.arrow_size = 10
        self._text_color = Qt.darkGray
        self._font = QFont("Arial", 9, QFont.Bold)
        self.control_point_offset = QPointF(0,0)

        self.setPen(QPen(Qt.darkCyan, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1) 
        self.update_path()

    def boundingRect(self):
        extra = (self.pen().width() + self.arrow_size) / 2.0 + 10
        return self.path().boundingRect().adjusted(-extra, -extra-15, extra, extra+5)


    def shape(self): 
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(10 + self.pen().width()) 
        return path_stroker.createStroke(self.path())


    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath()) 
            return

        line = QLineF(self.start_item.sceneBoundingRect().center(), 
                      self.end_item.sceneBoundingRect().center())
        
        start_point = self._get_intersection_point(self.start_item, line)
        end_point = self._get_intersection_point(self.end_item, QLineF(line.p2(), line.p1()))

        if start_point is None: start_point = line.p1()
        if end_point is None: end_point = line.p2()    

        path = QPainterPath(start_point)

        if self.start_item == self.end_item:
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.5
            loop_radius_y = rect.height() * 0.5
            
            c_x, c_y = rect.center().x(), rect.top()
            path.moveTo(c_x + loop_radius_x * 0.3, c_y - loop_radius_y * 0.1)
            path.cubicTo(c_x + loop_radius_x * 1.2, c_y - loop_radius_y * 1.2,
                          c_x - loop_radius_x * 0.8, c_y - loop_radius_y * 1.2,
                          c_x - loop_radius_x * 0.3, c_y - loop_radius_y * 0.1)
            end_point = path.currentPosition()
        else:
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2
            
            ctrl_pt = QPointF(mid_x + self.control_point_offset.x(), mid_y + self.control_point_offset.y())
            
            if self.control_point_offset.isNull():
                 path.lineTo(end_point)
            else:
                 path.quadTo(ctrl_pt, end_point)
        
        self.setPath(path)
        self.prepareGeometryChange()

    def _get_intersection_point(self, item, line):
        item_rect = item.sceneBoundingRect()
        points = []
        
        intersection_point = QPointF() # Reusable QPointF for intersection results

        # Top edge
        top_line = QLineF(item_rect.topLeft(), item_rect.topRight())
        intersect_type = line.intersect(top_line, intersection_point)
        if intersect_type == QLineF.BoundedIntersection: points.append(QPointF(intersection_point))
        
        # Bottom edge
        bottom_line = QLineF(item_rect.bottomLeft(), item_rect.bottomRight())
        intersect_type = line.intersect(bottom_line, intersection_point)
        if intersect_type == QLineF.BoundedIntersection: points.append(QPointF(intersection_point))

        # Left edge
        left_line = QLineF(item_rect.topLeft(), item_rect.bottomLeft())
        intersect_type = line.intersect(left_line, intersection_point)
        if intersect_type == QLineF.BoundedIntersection: points.append(QPointF(intersection_point))

        # Right edge
        right_line = QLineF(item_rect.topRight(), item_rect.bottomRight())
        intersect_type = line.intersect(right_line, intersection_point)
        if intersect_type == QLineF.BoundedIntersection: points.append(QPointF(intersection_point))


        if not points: return item_rect.center() 

        closest_point = points[0]
        min_dist_sq = QLineF(line.p1(), closest_point).length()**2
        for pt in points[1:]:
            dist_sq = QLineF(line.p1(), pt).length()**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point


    def paint(self, painter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        if self.path().elementCount() < 1 : return 

        line_end_point = self.path().pointAtPercent(1.0)
        angle_rad = 0
        if self.path().elementCount() > 0:
            p_before_end = self.path().pointAtPercent(0.98) # Point slightly before the end
            # Ensure p_before_end is different from line_end_point to get a valid angle
            if (line_end_point - p_before_end).manhattanLength() < 0.1: # If too close, use start of path
                if self.path().elementCount() > 0:
                    first_element = self.path().elementAt(0)
                    p_start = QPointF(first_element.x, first_element.y)
                    angle_rad = math.atan2(line_end_point.y() - p_start.y(), line_end_point.x() - p_start.x())
                else: # Cannot determine angle
                    return
            else:
                 angle_rad = math.atan2(line_end_point.y() - p_before_end.y(), line_end_point.x() - p_before_end.x())
        else:
            return


        arrow_p1_x = line_end_point.x() - self.arrow_size * math.cos(angle_rad + math.pi / 6)
        arrow_p1_y = line_end_point.y() - self.arrow_size * math.sin(angle_rad + math.pi / 6)
        arrow_p2_x = line_end_point.x() - self.arrow_size * math.cos(angle_rad - math.pi / 6)
        arrow_p2_y = line_end_point.y() - self.arrow_size * math.sin(angle_rad - math.pi / 6)

        painter.setBrush(self.pen().color())
        painter.drawPolygon(QPolygonF([line_end_point, QPointF(arrow_p1_x, arrow_p1_y), QPointF(arrow_p2_x, arrow_p2_y)]))


        if self.text_label:
            painter.setPen(self._text_color)
            painter.setFont(self._font)
            
            text_pos_on_path = self.path().pointAtPercent(0.5)
            tangent_angle_at_mid_rad = 0
            p_before_mid = self.path().pointAtPercent(0.49)
            p_after_mid = self.path().pointAtPercent(0.51)
            if (p_after_mid - p_before_mid).manhattanLength() < 0.1 and self.path().elementCount() > 0:
                first_element = self.path().elementAt(0)
                p_start = QPointF(first_element.x, first_element.y)
                tangent_angle_at_mid_rad = math.atan2(text_pos_on_path.y() - p_start.y(), text_pos_on_path.x() - p_start.x())
            else:
                tangent_angle_at_mid_rad = math.atan2(p_after_mid.y() - p_before_mid.y(), p_after_mid.x() - p_before_mid.x())

            offset_dist = 15 
            dx = -offset_dist * math.sin(tangent_angle_at_mid_rad)
            dy = offset_dist * math.cos(tangent_angle_at_mid_rad)

            text_rect = painter.fontMetrics().boundingRect(self.text_label)
            text_final_pos = text_pos_on_path + QPointF(dx - text_rect.width()/2, dy + text_rect.height()/4)

            painter.drawText(text_final_pos, self.text_label)

        if self.isSelected():
            selection_pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.shape()) 
    
    def get_data(self):
        return {
            'source': self.start_item.text_label,
            'target': self.end_item.text_label,
            'label': self.text_label,
            'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y()
        }
    
    def set_text(self, text):
        self.text_label = text
        self.prepareGeometryChange() 
        self.update()

    def set_control_point_offset(self, offset):
        self.control_point_offset = offset
        self.update_path()

# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item 

        if isinstance(item, GraphicsTransitionItem):
            self.start_item_name = item.start_item.text_label
            self.end_item_name = item.end_item.text_label

    def redo(self):
        self.scene.addItem(self.item_instance)
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
                self.item_instance.update_path()
            else: 
                 print(f"Warning: Could not fully re-link transition for redo: {self.item_instance.text_label}")

        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        self.scene.removeItem(self.item_instance)
        self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_instances = sorted(list(items_to_remove), 
                                              key=lambda x: 0 if isinstance(x, GraphicsStateItem) else 1)
        self.transition_connections = []
        for item in self.removed_items_instances:
            if isinstance(item, GraphicsTransitionItem):
                self.transition_connections.append({
                    'trans_item': item,
                    'start_name': item.start_item.text_label if item.start_item else None,
                    'end_name': item.end_item.text_label if item.end_item else None
                })
        
    def redo(self): 
        for item_instance in self.removed_items_instances:
            if item_instance.scene() == self.scene:
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): 
        for item_instance in self.removed_items_instances:
            if isinstance(item_instance, GraphicsStateItem):
                if item_instance.scene() is None:
                    self.scene.addItem(item_instance)
        
        for conn_info in self.transition_connections:
            trans_item = conn_info['trans_item']
            if trans_item.scene() is None:
                self.scene.addItem(trans_item)
            
            start_node = self.scene.get_state_by_name(conn_info['start_name'])
            end_node = self.scene.get_state_by_name(conn_info['end_name'])

            if start_node and end_node:
                trans_item.start_item = start_node
                trans_item.end_item = end_node
                trans_item.update_path()
            else:
                print(f"Warning (Undo Remove): Could not re-link transition '{trans_item.text_label}'. Missing states.")

        for item_instance in self.removed_items_instances:
            if not isinstance(item_instance, (GraphicsStateItem, GraphicsTransitionItem)):
                if item_instance.scene() is None:
                     self.scene.addItem(item_instance)

        self.scene.set_dirty(True)


class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_positions_new, description="Move Items"):
        super().__init__(description)
        self.items_positions_new = items_positions_new 
        self.items_positions_old = []
        self.scene_ref = None
        for item, _ in self.items_positions_new:
            self.items_positions_old.append((item, item.pos())) 
            if not self.scene_ref : self.scene_ref = item.scene()


    def redo(self):
        if not self.scene_ref: return
        for item, new_pos in self.items_positions_new:
            item.setPos(new_pos)
        self.scene_ref.set_dirty(True)
    
    def undo(self):
        if not self.scene_ref: return
        for item, old_pos in self.items_positions_old:
            item.setPos(old_pos)
        self.scene_ref.set_dirty(True)

class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props, new_props, description="Edit Properties"):
        super().__init__(description)
        self.item = item
        self.old_props = old_props 
        self.new_props = new_props 
        self.scene_ref = item.scene()

    def redo(self):
        if isinstance(self.item, GraphicsStateItem):
            self.item.set_properties(self.new_props['name'], self.new_props['is_initial'], self.new_props['is_final'])
        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_text(self.new_props['label'])
            if 'control_offset_x' in self.new_props and 'control_offset_y' in self.new_props:
                 self.item.set_control_point_offset(QPointF(self.new_props['control_offset_x'], self.new_props['control_offset_y']))
        self.scene_ref.set_dirty(True)
        self.item.update() 

    def undo(self):
        if isinstance(self.item, GraphicsStateItem):
            self.item.set_properties(self.old_props['name'], self.old_props['is_initial'], self.old_props['is_final'])
        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_text(self.old_props['label'])
            if 'control_offset_x' in self.old_props and 'control_offset_y' in self.old_props:
                 self.item.set_control_point_offset(QPointF(self.old_props['control_offset_x'], self.old_props['control_offset_y']))
        self.scene_ref.set_dirty(True)
        self.item.update()


# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 4000, 3000) 
        self.current_mode = "select"
        self.transition_start_item = None
        self.log_function = print
        self.undo_stack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {}
        self._temp_transition_line = None 

        self.item_moved.connect(self._handle_item_moved)
        self.setBackgroundBrush(QColor(245, 245, 245)) 

    def get_state_by_name(self, name):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty)
            
    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode):
        old_mode = self.current_mode
        self.current_mode = mode
        self.transition_start_item = None 
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None

        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            for item in self.items(): 
                if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, True)
        elif mode in ["state", "transition"]:
            QApplication.setOverrideCursor(Qt.CrossCursor)
            for item in self.items(): 
                 if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        else: 
            if old_mode in ["state", "transition"] and mode != old_mode:
                QApplication.restoreOverrideCursor()


    def select_all(self):
        for item in self.items():
            item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            for item in self.items():
                if isinstance(item, GraphicsTransitionItem):
                    if item.start_item == moved_item or item.end_item == moved_item:
                        item.update_path()

    def mousePressEvent(self, event):
        pos = event.scenePos()
        item_at_pos = self.itemAt(pos, QTransform())
        state_items_under_cursor = [it for it in self.items(pos) if isinstance(it, GraphicsStateItem)]
        top_state_item = state_items_under_cursor[0] if state_items_under_cursor else None

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                self._add_state_item(pos)
            elif self.current_mode == "transition":
                if top_state_item:
                    self._handle_transition_click(top_state_item, pos)
                else: 
                    self.transition_start_item = None
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
                    self.log_function("Transition drawing cancelled (clicked empty space).")
            else: # Select mode
                self._mouse_press_items_positions.clear()
                selected_movable_items = [item for item in self.selectedItems() if item.flags() & QGraphicsItem.ItemIsMovable]
                for item in selected_movable_items:
                     self._mouse_press_items_positions[item] = item.pos()
                super().mousePressEvent(event) 
                return 
        elif event.button() == Qt.RightButton:
            target_item_for_menu = None
            if top_state_item:
                target_item_for_menu = top_state_item
            elif item_at_pos and isinstance(item_at_pos, GraphicsTransitionItem):
                 target_item_for_menu = item_at_pos
            
            if target_item_for_menu:
                if not target_item_for_menu.isSelected():
                    self.clearSelection()
                    target_item_for_menu.setSelected(True)
                self._show_context_menu(target_item_for_menu, event.screenPos())
            else: 
                self.clearSelection()
        else: 
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(), event.scenePos()))
            self.update() 
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions: 
                moved_items_data = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    if item.pos() != old_pos : 
                        moved_items_data.append((item, item.pos())) 
                
                if moved_items_data:
                    cmd = MoveItemsCommand(moved_items_data)
                    self.undo_stack.push(cmd)
                self._mouse_press_items_positions.clear()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        state_items_under_cursor = [it for it in self.items(event.scenePos()) if isinstance(it, GraphicsStateItem)]
        item_to_edit = state_items_under_cursor[0] if state_items_under_cursor else item

        if isinstance(item_to_edit, (GraphicsStateItem, GraphicsTransitionItem)):
            self.edit_item_properties(item_to_edit)
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        edit_action = menu.addAction("Properties...")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec_(global_pos)
        if action == edit_action:
            self.edit_item_properties(item)
        elif action == delete_action:
            if not item.isSelected():
                self.clearSelection()
                item.setSelected(True)
            self.delete_selected_items() 

    def edit_item_properties(self, item):
        if isinstance(item, GraphicsStateItem):
            old_props = {'name': item.text_label, 'is_initial': item.is_initial, 'is_final': item.is_final}
            dialog = StatePropertiesDialog(item.text_label, item.is_initial, item.is_final)
            if dialog.exec_() == QDialog.Accepted:
                new_name = dialog.get_name()
                if new_name != item.text_label and self.get_state_by_name(new_name):
                    QMessageBox.warning(None, "Duplicate Name", f"A state with the name '{new_name}' already exists.")
                    return
                
                new_props = {'name': new_name, 
                             'is_initial': dialog.is_initial_cb.isChecked(), 
                             'is_final': dialog.is_final_cb.isChecked()}
                cmd = EditItemPropertiesCommand(item, old_props, new_props, "Edit State Properties")
                self.undo_stack.push(cmd)
                self.log_function(f"Properties updated for state: {new_name}")

        elif isinstance(item, GraphicsTransitionItem):
            old_props = {
                'label': item.text_label,
                'control_offset_x': item.control_point_offset.x(),
                'control_offset_y': item.control_point_offset.y()
            }
            dialog = TransitionPropertiesDialog(item.text_label, item.control_point_offset)
            if dialog.exec_() == QDialog.Accepted:
                new_props = {
                    'label': dialog.get_label(),
                    'control_offset_x': dialog.get_control_offset().x(),
                    'control_offset_y': dialog.get_control_offset().y()
                }
                cmd = EditItemPropertiesCommand(item, old_props, new_props, "Edit Transition Properties")
                self.undo_stack.push(cmd)
                self.log_function(f"Properties updated for transition: {new_props['label']}")
        self.update() 

    def _add_state_item(self, pos, name_prefix="State"):
        i = 1
        while self.get_state_by_name(f"{name_prefix}{i}"):
            i += 1
        default_name = f"{name_prefix}{i}"

        state_name, ok = QInputDialog.getText(None, "New State", "Enter state name:", text=default_name)
        if ok and state_name:
            if self.get_state_by_name(state_name):
                QMessageBox.warning(None, "Duplicate Name", f"A state with the name '{state_name}' already exists.")
                self.set_mode("select")
                return

            props_dialog = StatePropertiesDialog(state_name) 
            if props_dialog.exec_() == QDialog.Accepted:
                new_state = GraphicsStateItem(
                    pos.x() - 60, pos.y() - 30, 120, 60,
                    props_dialog.get_name(),
                    props_dialog.is_initial_cb.isChecked(),
                    props_dialog.is_final_cb.isChecked()
                )
                cmd = AddItemCommand(self, new_state, "Add State")
                self.undo_stack.push(cmd)
                self.log_function(f"Added state: {new_state.text_label}")
        self.set_mode("select")

    def _handle_transition_click(self, clicked_state_item, click_pos):
        if not self.transition_start_item:
            self.transition_start_item = clicked_state_item
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem() 
                self._temp_transition_line.setPen(QPen(Qt.DashLine))
                self.addItem(self._temp_transition_line)
            
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos))
            self.log_function(f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else:
            if self._temp_transition_line:
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            label, ok = QInputDialog.getText(None, "New Transition", "Enter transition label (optional):")
            if ok: 
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, label)
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{label}]")
            
            self.transition_start_item = None 
            self.set_mode("select") 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self.selectedItems():
                self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line:
                    self.removeItem(self._temp_transition_line)
                    self._temp_transition_line = None
                self.log_function("Transition drawing cancelled.")
                self.set_mode("select")
            else:
                self.clearSelection()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return

        items_to_delete_directly = set(selected)
        related_transitions_to_delete = set()
        for item in list(items_to_delete_directly): 
            if isinstance(item, GraphicsStateItem):
                for scene_item in self.items():
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            related_transitions_to_delete.add(scene_item)
        
        all_items_to_delete = items_to_delete_directly.union(related_transitions_to_delete)
        
        if all_items_to_delete:
            cmd = RemoveItemsCommand(self, list(all_items_to_delete), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Deleted {len(all_items_to_delete)} item(s).")
            self.clearSelection() 


    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-state-tool"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-state-tool"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-state-tool"):
            dropped_text = event.mimeData().text() 
            self._add_state_item(pos, name_prefix=dropped_text or "State")
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': []} 
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                data['transitions'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear() 
        self.set_dirty(False) 

        state_items_map = {} 

        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'],
                state_data.get('width', 120), state_data.get('height', 60),
                state_data['name'],
                state_data.get('is_initial', False),
                state_data.get('is_final', False)
            )
            self.addItem(state_item)
            state_items_map[state_data['name']] = state_item

        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source'])
            tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(src_item, tgt_item, trans_data.get('label', ''))
                trans_item.set_control_point_offset(QPointF(
                    trans_data.get('control_offset_x', 0),
                    trans_data.get('control_offset_y', 0)
                ))
                self.addItem(trans_item)
            else:
                self.log_function(f"Warning: Could not link transition '{trans_data.get('label')}' due to missing states: {trans_data['source']} or {trans_data['target']}.")
        
        self.set_dirty(False) 
        self.undo_stack.clear()

# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, state_name="", initial=False, final=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        layout = QFormLayout(self)

        self.name_edit = QLineEdit(state_name)
        layout.addRow("Name:", self.name_edit)

        self.is_initial_cb = QCheckBox()
        self.is_initial_cb.setChecked(initial)
        layout.addRow("Initial State:", self.is_initial_cb)

        self.is_final_cb = QCheckBox()
        self.is_final_cb.setChecked(final)
        layout.addRow("Final State:", self.is_final_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_name(self): return self.name_edit.text()

class TransitionPropertiesDialog(QDialog):
    def __init__(self, label="", control_offset=QPointF(0,0), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        layout = QFormLayout(self)

        self.label_edit = QLineEdit(label)
        layout.addRow("Label:", self.label_edit)

        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-500, 500)
        self.offset_x_spin.setValue(int(control_offset.x()))
        layout.addRow("Curve Offset X:", self.offset_x_spin)

        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-500, 500)
        self.offset_y_spin.setValue(int(control_offset.y()))
        layout.addRow("Curve Offset Y:", self.offset_y_spin)


        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_label(self): return self.label_edit.text()
    def get_control_offset(self): return QPointF(self.offset_x_spin.value(), self.offset_y_spin.value())


class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)

        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout() 
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        path_form_layout.addRow("Path:", self.path_edit)
        
        btn_layout = QHBoxLayout()
        auto_detect_btn = QPushButton("Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        btn_layout.addWidget(auto_detect_btn)
        btn_layout.addWidget(browse_btn)
        btn_layout.addStretch() 
        
        path_v_layout = QVBoxLayout() 
        path_v_layout.addLayout(path_form_layout)
        path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout)
        main_layout.addWidget(path_group)


        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout()
        self.test_status_label = QLabel("Status: Unknown")
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label) 
        test_layout.addWidget(test_btn)
        test_layout.addWidget(self.test_status_label)
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        self._update_test_label_from_signal(self.matlab_connection.connected, "Initial status check.")


    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting...")
        QApplication.processEvents()
        if self.matlab_connection.detect_matlab(): 
            self.path_edit.setText(self.matlab_connection.matlab_path)

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", QDir.homePath(), exe_filter)
        if path:
            self.path_edit.setText(path)
            self.test_status_label.setText("Status: Path selected. Test or Apply to confirm.")
            self.test_status_label.setStyleSheet("") 

    def _test_connection_and_update_label(self):
        path = self.path_edit.text()
        if not path:
            self._update_test_label_from_signal(False, "Path is empty.")
            return

        self.test_status_label.setText("Status: Testing connection with current path...")
        self.test_status_label.setStyleSheet("")
        QApplication.processEvents()
        
        original_path = self.matlab_connection.matlab_path
        original_connected_status = self.matlab_connection.connected

        self.matlab_connection.set_matlab_path(path) 
        if self.matlab_connection.connected: 
            self.matlab_connection.test_connection() 


    def _update_test_label_from_signal(self, success, message):
        status_text = "Status: " + ("Connected. " if success else "Disconnected. ") + message
        self.test_status_label.setText(status_text)
        self.test_status_label.setStyleSheet("color: green;" if success else "color: red;")
        if success:
             self.path_edit.setText(self.matlab_connection.matlab_path) 

    def _apply_settings(self):
        path = self.path_edit.text()
        if not self.matlab_connection.set_matlab_path(path) and path:
            QMessageBox.warning(self, "Invalid Path", 
                                self.test_status_label.text().replace("Status: ", "") + 
                                "\nPlease ensure the path is correct.")
            return 

        if not path:
            self.matlab_connection.set_matlab_path("") 
            self.accept()
            return

        if self.matlab_connection.connected:
            self.matlab_connection.test_connection()
            if not self.matlab_connection.connected: 
                QMessageBox.warning(self, "MATLAB Connection Test Failed",
                                    self.test_status_label.text().replace("Status: ", "") +
                                    "\nSettings applied, but MATLAB could not be reached.")
        self.accept()

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)
        
        self.scene = DiagramScene(self.undo_stack, self)
        self.scene.set_log_function(self.log_message)
        # This connection is correct for updating the modified state of the window
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) 
        # This connection updates the title string when the modified state changes
        self.scene.modifiedStatusChanged.connect(self._update_window_title) 


        self.init_ui()
        self._update_matlab_status_display(False, "Not Connected. Configure in Simulation menu.")
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_actions_enabled_state)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished) 

        # self.setWindowTitle(f"{APP_NAME}") # This initial setWindowTitle is okay, but _update_window_title will refine it
        self._update_window_title() # Call this to set the initial title correctly with placeholder
        self.on_new_file(silent=True)  

    def init_ui(self):
        self.setGeometry(100, 100, 1400, 900)
        
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks()
        self._create_central_widget()

        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state() 
        self._update_undo_redo_actions_enable_state()

    def _create_actions(self):
        # Helper to safely get QStyle enum values
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            # Returns the integer value of the enum
            try:
                return getattr(QStyle, attr_name)
            except AttributeError:
                # Optional: Make warning less intrusive or log it differently
                # print(f"Debug: QStyle attribute '{attr_name}' not found.") 
                if fallback_attr_name:
                    try:
                        # print(f"Debug: Trying fallback QStyle attribute '{fallback_attr_name}'.")
                        return getattr(QStyle, fallback_attr_name)
                    except AttributeError:
                        # print(f"Debug: Fallback QStyle attribute '{fallback_attr_name}' also not found.")
                        pass # Suppress further messages if fallback also fails
                return QStyle.SP_CustomBase 


        # File
        self.new_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileIcon"), "New"), "&New", self, shortcut="Ctrl+N", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DialogOpenButton"), "Opn"), "&Open...", self, shortcut="Ctrl+O", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DialogSaveButton"), "Sav"), "&Save", self, shortcut="Ctrl+S", triggered=self.on_save_file)
        self.save_as_action = QAction("Save &As...", self, shortcut="Ctrl+Shift+S", triggered=self.on_save_file_as)
        self.exit_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DialogCloseButton"), "Exit"), "E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        # Edit
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setIcon(get_standard_icon(_safe_get_style_enum("SP_ArrowBack", "SP_ArrowLeft"), "Un"))
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.setIcon(get_standard_icon(_safe_get_style_enum("SP_ArrowForward", "SP_ArrowRight"), "Re"))
        
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)

        self.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut="Ctrl+A", triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(_safe_get_style_enum("SP_TrashIcon"), "Del"), "&Delete", self, shortcut="Delete", triggered=self.on_delete_selected)
        
        # Scene Interaction Modes
        self.mode_action_group = QActionGroup(self)
        
        select_icon_enum_val = _safe_get_style_enum("SP_ArrowCursor")
        if select_icon_enum_val == QStyle.SP_CustomBase: # If SP_ArrowCursor was not found and defaulted
            select_icon_enum_val = _safe_get_style_enum("SP_PointingHandCursor") # Try SP_PointingHandCursor

        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(select_icon_enum_val, "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select"))
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(_safe_get_style_enum("SP_FileDialogNewFolder"), "St")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state"))
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(_safe_get_style_enum("SP_FileDialogBack", "SP_ArrowLeft"), "Tr")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition"))
        
        self.mode_action_group.addAction(self.select_mode_action)
        self.mode_action_group.addAction(self.add_state_mode_action)
        self.mode_action_group.addAction(self.add_transition_mode_action)
        self.select_mode_action.setChecked(True) 

        # Simulation
        self.export_simulink_action = QAction(QIcon.fromTheme("document-export", get_standard_icon(_safe_get_style_enum("SP_ArrowRight"), "->M")), "&Export to Simulink...", self, triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(QIcon.fromTheme("media-playback-start", get_standard_icon(_safe_get_style_enum("SP_MediaPlay"), "Run")), "&Run Simulation...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(QIcon.fromTheme("utilities-terminal", get_standard_icon(_safe_get_style_enum("SP_ComputerIcon"), "Cde")), "Generate &Code (C/C++)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(QIcon.fromTheme("preferences-system", get_standard_icon(_safe_get_style_enum("SP_ComputerIcon", "SP_DesktopIcon"), "Cfg")), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)

        # Help
        self.about_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DialogHelpButton"), "?"), "&About", self, triggered=self.on_about)


    def _create_menus(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Edit Menu
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu("Interaction Mode")
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)


        # Simulation Menu
        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(self.run_simulation_action)
        sim_menu.addAction(self.generate_code_action)
        sim_menu.addSeparator()
        sim_menu.addAction(self.matlab_settings_action)

        # View Menu (for docks)
        self.view_menu = menu_bar.addMenu("&View")

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        # File Toolbar
        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        # Edit Toolbar
        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolBar")
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addAction(self.delete_action)
        
        # Tools Toolbar
        tools_toolbar = self.addToolBar("Tools")
        tools_toolbar.setObjectName("ToolsToolBar")
        tools_toolbar.addAction(self.select_mode_action)
        tools_toolbar.addAction(self.add_state_mode_action)
        tools_toolbar.addAction(self.add_transition_mode_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1) 

        self.matlab_status_label = QLabel("MATLAB: Not Connected")
        self.matlab_status_label.setToolTip("MATLAB connection status. Configure in Simulation > MATLAB Settings.")
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0,0) 
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)


    def _create_docks(self):
        # Toolbox Dock
        self.toolbox_dock = QDockWidget("Toolbox", self)
        self.toolbox_dock.setObjectName("ToolboxDock")
        toolbox_widget = QWidget()
        toolbox_layout = QVBoxLayout(toolbox_widget)
        
        state_button = DraggableToolButton("State", "application/x-state-tool", "background-color: #add8e6;") 
        toolbox_layout.addWidget(state_button)
        
        toolbox_layout.addStretch()
        self.toolbox_dock.setWidget(toolbox_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.toolbox_dock)
        self.view_menu.addAction(self.toolbox_dock.toggleViewAction())

        # Log Dock
        self.log_dock = QDockWidget("Log Output", self)
        self.log_dock.setObjectName("LogDock")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_dock.setWidget(self.log_output)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())
        
        # Properties Dock (Placeholder - could be expanded)
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_editor = QLabel("Select an item to see its properties here.") 
        self.properties_editor.setAlignment(Qt.AlignCenter)
        self.properties_dock.setWidget(self.properties_editor)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.view_menu.addAction(self.properties_dock.toggleViewAction())


    def _create_central_widget(self):
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag) 
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate) 
        self.setCentralWidget(self.view)

    def log_message(self, message):
        self.log_output.append(message)
        self.status_label.setText(message.split('\n')[0][:100]) 
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready")) 

    def _update_window_title(self):
        title = APP_NAME
        if self.current_file_path:
            title += f" - {os.path.basename(self.current_file_path)}"
        else:
            title += " - Untitled"
        
        # This is the crucial part: always include [*] when setting the title string
        # The self.isWindowModified() call will then determine if the asterisk is shown or hidden.
        title += "[*]" 
        self.setWindowTitle(title)

    def _update_save_actions_enable_state(self):
        is_dirty = self.scene.is_dirty()
        self.save_action.setEnabled(is_dirty)

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())

    def _update_matlab_status_display(self, connected, message):
        self.matlab_status_label.setText(f"MATLAB: {'Connected' if connected else 'Disconnected'}")
        self.matlab_status_label.setStyleSheet("color: green;" if connected else "color: red;")
        self.log_message(f"MATLAB Status: {message}")
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        connected = self.matlab_connection.connected
        self.export_simulink_action.setEnabled(connected)
        self.run_simulation_action.setEnabled(connected)
        self.generate_code_action.setEnabled(connected)

    def _start_matlab_operation(self, operation_name):
        self.log_message(f"{operation_name} started...")
        self.progress_bar.setVisible(True)
        self.centralWidget().setEnabled(False) 

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False)
        self.centralWidget().setEnabled(True)


    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Process: {message}")
        if success:
            if "Model generation" in message and data: 
                 QMessageBox.information(self, "Simulink Model Generation", 
                                        f"Model generated successfully:\n{data}")
                 self.last_generated_model_path = data
            elif "Simulation" in message:
                 QMessageBox.information(self, "Simulation", f"Simulation finished successfully.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)
        
    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Code Generation: {message}")
        if success and output_dir:
            QMessageBox.information(self, "Code Generation", 
                                    f"Code generation successful.\nOutput directory:\n{output_dir}")
            reply = QMessageBox.question(self, "Open Output Directory", 
                                         "Do you want to open the output directory?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                if sys.platform == "win32":
                    os.startfile(output_dir)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", output_dir])
                else:
                    subprocess.Popen(["xdg-open", output_dir])


        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)


    # --- File Operations ---
    def _prompt_save_if_dirty(self):
        if not self.scene.is_dirty():
            return True 
        
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes",
                                     f"The document '{file_name}' has been modified.\n"
                                     "Do you want to save your changes?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if reply == QMessageBox.Save:
            return self.on_save_file()
        elif reply == QMessageBox.Cancel:
            return False 
        return True 

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty():
            return
        self.scene.clear()
        self.scene.set_dirty(False)
        self.current_file_path = None
        self.undo_stack.clear()
        self._update_window_title()
        self.log_message("New file created.")
        self.select_mode_action.trigger() 

    def on_open_file(self):
        if not self._prompt_save_if_dirty():
            return
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", QDir.homePath(), FILE_FILTER)
        if file_path:
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.scene.set_dirty(False) 
                self.undo_stack.clear()
                self._update_window_title()
                self.log_message(f"File opened: {file_path}")
                self.view.ensureVisible(self.scene.itemsBoundingRect()) 
            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load file: {file_path}")


    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                self.log_message(f"Error: Invalid file format in {file_path}")
                return False
            self.scene.load_diagram_data(data)
            return True
        except Exception as e:
            self.log_message(f"Error loading file {file_path}: {str(e)}")
            QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{str(e)}")
            return False

    def on_save_file(self):
        if self.current_file_path:
            return self._save_to_path(self.current_file_path)
        else:
            return self.on_save_file_as()

    def on_save_file_as(self):
        default_filename = os.path.basename(self.current_file_path) if self.current_file_path else "untitled" + FILE_EXTENSION
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File As", 
                                                   os.path.join(QDir.homePath(), default_filename), 
                                                   FILE_FILTER)
        if file_path:
            if not file_path.endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            if self._save_to_path(file_path):
                self.current_file_path = file_path
                self._update_window_title() 
                return True
        return False

    def _save_to_path(self, file_path):
        try:
            data = self.scene.get_diagram_data()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            self.scene.set_dirty(False)
            self.log_message(f"File saved: {file_path}")
            return True
        except Exception as e:
            self.log_message(f"Error saving file {file_path}: {str(e)}")
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{str(e)}")
            return False
            
    # --- Action Handlers ---
    def on_select_all(self):
        self.scene.select_all()

    def on_delete_selected(self):
        self.scene.delete_selected_items() 

    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Error", "MATLAB not connected. Configure settings first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        layout = QFormLayout(dialog)
        
        model_name_edit = QLineEdit("BrainStateMachine")
        layout.addRow("Model Name:", model_name_edit)

        output_dir_edit = QLineEdit(os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        browse_btn = QPushButton("Browse...")
        def browse_dir():
            d = QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn.clicked.connect(browse_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(output_dir_edit)
        dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text()
            output_dir = output_dir_edit.text()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified.")
                return
            
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except OSError as e:
                    QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                    return

            diagram_data = self.scene.get_diagram_data()
            self._start_matlab_operation("Simulink model generation")
            self.matlab_connection.generate_simulink_model(
                diagram_data['states'], diagram_data['transitions'], output_dir, model_name
            )

    def on_run_simulation(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Error", "MATLAB not connected.")
            return

        default_model_path = getattr(self, 'last_generated_model_path', "")
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model (.slx)", 
                                                   default_model_path or QDir.homePath(), 
                                                   "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Enter simulation time (seconds):", 10.0, 0.1, 10000, 1)
        if not ok: return

        self._start_matlab_operation("Simulink simulation")
        self.matlab_connection.run_simulation(model_path, sim_time)


    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Error", "MATLAB not connected.")
            return

        default_model_path = getattr(self, 'last_generated_model_path', "")
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model (.slx) for Code Generation",
                                                   default_model_path or QDir.homePath(),
                                                   "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        dialog = QDialog(self)
        dialog.setWindowTitle("Generate Code Options")
        layout = QFormLayout(dialog)

        lang_combo = QComboBox()
        lang_combo.addItems(["C", "C++"])
        lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)

        output_dir_edit = QLineEdit(os.path.dirname(model_path)) 
        browse_btn = QPushButton("Browse...")
        def browse_dir_codegen():
            d = QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory for Code", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn.clicked.connect(browse_dir_codegen)
        dir_layout_codegen = QHBoxLayout()
        dir_layout_codegen.addWidget(output_dir_edit)
        dir_layout_codegen.addWidget(browse_btn)
        layout.addRow("Base Output Directory:", dir_layout_codegen)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory must be specified.")
                return
            
            if not os.path.exists(output_dir_base):
                 try: os.makedirs(output_dir_base, exist_ok=True)
                 except OSError as e:
                     QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                     return

            self._start_matlab_operation("Code generation")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(self.matlab_connection, self)
        dialog.exec_() 

    def on_about(self):
        QMessageBox.about(self, "About " + APP_NAME,
                          f"<b>{APP_NAME}</b> v{APP_VERSION}\n\n"
                          "A graphical tool for designing state machines and "
                          "interacting with MATLAB/Simulink.\n\n"
                          "(c) 2024 Your Name/Organization")


    def closeEvent(self, event):
        if self._prompt_save_if_dirty():
            for thread in list(self.matlab_connection._active_threads): 
                if thread.isRunning():
                    print(f"Warning: MATLAB thread {thread} still running on exit.")
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())