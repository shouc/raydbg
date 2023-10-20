import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.ApiGraphs


class RayActorTopLevel extends DataFlow::Node {
    RayActorTopLevel() {
        exists(API::CallNode remoteFunc |
            remoteFunc = API::moduleImport("ray").getMember("remote").getACall() and
            this = remoteFunc.getArg(0)
        )
    }
}

class RayActorFull extends DataFlow::Node {
    RayActorFull() {
        // either it is a top level actor
        this instanceof RayActorTopLevel
        or
        // or it is a function that can be reached by actors
        exists(RayActorFull toplevel, Call call, Name name |
            call.getFunc() = name and
            this.asExpr().(FunctionExpr).getName() = name.getId() and
            toplevel.asExpr().(FunctionExpr).contains(call)
        )
    }
}


class RayDriverCall extends DataFlow::Node {
    RayDriverCall() {
        exists(Call c|
            this.asExpr() = c
            and c.getFunc().(Attribute).getAttr() = "remote" // and
            // actor.asExpr().(FunctionExpr).getName() = c.getFunc().(Attribute).getObject().(Name).getId()
        )
    }
}



class RayDriverCallExpr extends Expr {
    RayDriverCallExpr() {
        exists(Call c|
            this = c
            and c.getFunc().(Attribute).getAttr() = "remote" // and
            // actor.asExpr().(FunctionExpr).getName() = c.getFunc().(Attribute).getObject().(Name).getId()
        )
    }
}


class RayGet extends DataFlow::Node {
    RayGet() {
        exists(Call c |
            this.asExpr() = c
            and c.getFunc().(Attribute).getAttr() = "get"
            and c.getFunc().(Attribute).getObject().(Name).getId().toString() = "ray"
        )
    }
}


class RayPut extends DataFlow::Node {
    RayPut() {
        exists(Call c |
            this.asExpr() = c
            and c.getFunc().(Attribute).getAttr() = "put"
            and c.getFunc().(Attribute).getObject().(Name).getId().toString() = "ray"
        )
    }
}

class GetToDriver extends DataFlow::Configuration {
    GetToDriver() { this = "GetToDriver" }

    override predicate isSource(DataFlow::Node source) {
        source instanceof RayGet
    }

    override predicate isSink(DataFlow::Node sink) {
        exists(RayDriverCall driver |
            sink.asExpr() = driver.asExpr().(Call).getAnArg()
        )
    }

}

class GetToDriverNoRW extends DataFlow::Configuration {
    GetToDriverNoRW() { this = "GetToDriverNoRW" }

    override predicate isSource(DataFlow::Node source) {
        source instanceof RayGet
    }

    override predicate isSink(DataFlow::Node sink) {
        exists(RayDriverCall driver |
            sink.asExpr() = driver.asExpr().(Call).getAnArg()
        )
    }
}

from GetToDriverNoRW config, DataFlow::Node source, DataFlow::Node sink
    where config.hasFlow(source, sink)
select source.asExpr(), sink.asExpr()
